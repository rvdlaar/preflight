/**
 * synthesis/archimate.mjs — ArchiMate .archimate XML parser.
 *
 * Traverses the hospital's Archi model to produce structured data for:
 *   - Step 0: Landscape context (existing apps, overlaps, lifecycle)
 *   - Step 2: Per-persona scoped retrieval
 *   - Step 4: STRIDE pre-fill (actual components, interfaces, data flows)
 *   - Step 5: Diagrams (cascade dependencies, integration flows)
 *   - BIV: Cascade impact analysis
 *
 * Also loads ZiRA reference model and surfaces conflicts:
 *   "ZiRA says bedrijfsfunctie X should be served by Y. Your model shows Z."
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

// ---------------------------------------------------------------------------
// ArchiMate element types we care about
// ---------------------------------------------------------------------------

const ELEMENT_LAYERS = {
  Business: ['BusinessActor', 'BusinessRole', 'BusinessFunction', 'BusinessProcess', 'BusinessService', 'BusinessObject', 'BusinessInteraction'],
  Application: ['ApplicationComponent', 'ApplicationFunction', 'ApplicationInterface', 'ApplicationService', 'DataObject', 'ApplicationInteraction'],
  Technology: ['Node', 'Device', 'SystemSoftware', 'TechnologyService', 'TechnologyInterface', 'Artifact', 'CommunicationPath', 'Network'],
  Motivation: ['Stakeholder', 'Driver', 'Assessment', 'Goal', 'Outcome', 'Principle', 'Requirement', 'Constraint', 'Meaning', 'Value'],
  Implementation: ['WorkPackage', 'Deliverable', 'ImplementationEvent', 'Plateau', 'Gap'],
};

const ALL_ELEMENT_TYPES = Object.values(ELEMENT_LAYERS).flat();

const RELATIONSHIP_TYPES = {
  Composition: { source: 'source', target: 'target', strength: 'strong' },
  Aggregation: { source: 'source', target: 'target', strength: 'medium' },
  Assignment: { source: 'source', target: 'target', strength: 'strong' },
  Realization: { source: 'source', target: 'target', strength: 'strong' },
  Serving: { source: 'source', target: 'target', strength: 'weak' },
  Access: { source: 'source', target: 'target', strength: 'weak' },
  Influence: { source: 'source', target: 'target', strength: 'weak' },
  Triggering: { source: 'source', target: 'target', strength: 'medium' },
  Flow: { source: 'source', target: 'target', strength: 'medium' },
  Specialization: { source: 'source', target: 'target', strength: 'strong' },
  Association: { source: 'source', target: 'target', strength: 'weak' },
};

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

/**
 * Parse an .archimate XML file and return a structured model.
 *
 * @param {string} filePath — path to .archimate file
 * @returns {object} { elements, relationships, folders, views }
 */
export function parseArchimate(filePath) {
  const xml = readFileSync(filePath, 'utf-8');
  return parseArchimateXml(xml);
}

/**
 * Parse ArchiMate XML string directly.
 */
export function parseArchimateXml(xml) {
  const elements = {};
  const relationships = [];
  const folders = {};
  const views = [];

  // Parse elements — <element xsi:type="BusinessFunction" id="..." name="..."/>
  const elemRegex = /<element\s+xsi:type="(\w+)"\s+id="([^"]+)"\s+name="([^"]*)"[^>]*\/?>/g;
  let match;
  while ((match = elemRegex.exec(xml)) !== null) {
    const [_, type, id, name] = match;
    const layer = findLayer(type);
    if (layer) {
      elements[id] = { id, type, name: decodeXml(name), layer, properties: {} };
    }
  }

  // Parse properties — <property key="..." value="..."/> inside elements
  const propRegex = /<property\s+key="([^"]+)"\s+value="([^"]*)"[^/]*\/>/g;
  // We need to find properties within their parent element context
  const elemBlockRegex = /<element\s+xsi:type="(\w+)"\s+id="([^"]+)"[^>]*>([\s\S]*?)<\/element>/g;
  while ((match = elemBlockRegex.exec(xml)) !== null) {
    const [_, type, id] = match;
    const body = match[3];
    if (elements[id]) {
      const props = {};
      let propMatch;
      const pr = /<property\s+key="([^"]+)"\s+value="([^"]*)"/g;
      while ((propMatch = pr.exec(body)) !== null) {
        props[propMatch[1]] = decodeXml(propMatch[2]);
      }
      elements[id].properties = props;
    }
  }

  // Parse relationships
  const relRegex = /<element\s+xsi:type="(\w+)"\s+id="([^"]+)"\s+source="([^"]+)"\s+target="([^"]+)"[^>]*\/?>/g;
  while ((match = relRegex.exec(xml)) !== null) {
    const [_, type, id, source, target] = match;
    if (RELATIONSHIP_TYPES[type]) {
      relationships.push({ id, type, source, target });
    } else if (type === 'Association' || type === 'Flow' || type === 'Serving' || type === 'Access' || type === 'Triggering') {
      relationships.push({ id, type, source, target });
    }
  }

  // Parse folders for organization
  const folderRegex = /<folder\s+id="([^"]+)"\s+name="([^"]*)"[^>]*\/?>/g;
  while ((match = folderRegex.exec(xml)) !== null) {
    folders[match[1]] = { id: match[1], name: decodeXml(match[2]) };
  }

  return { elements, relationships, folders, views };
}

function findLayer(type) {
  for (const [layer, types] of Object.entries(ELEMENT_LAYERS)) {
    if (types.includes(type)) return layer;
  }
  return null;
}

function decodeXml(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

// ---------------------------------------------------------------------------
// Query engine — answer specific questions about the model
// ---------------------------------------------------------------------------

/**
 * Find all application components in a capability space.
 * Used by Thomas (Application) in Step 0.
 */
export function findApplicationsByCapability(model, capabilityKeywords) {
  const keywords = capabilityKeywords.map(k => k.toLowerCase());
  const results = [];

  for (const elem of Object.values(model.elements)) {
    if (elem.type !== 'ApplicationComponent') continue;

    // Check if the component serves a business function matching keywords
    const servedFunctions = getRelatedTargets(model, elem.id, 'Serving')
      .filter(t => model.elements[t]?.type === 'BusinessFunction');

    const matches = keywords.some(kw =>
      elem.name.toLowerCase().includes(kw) ||
      Object.values(elem.properties).some(v => v.toLowerCase().includes(kw)) ||
      servedFunctions.some(fId => model.elements[fId]?.name.toLowerCase().includes(kw))
    );

    if (matches) {
      results.push({
        id: elem.id,
        name: elem.name,
        properties: elem.properties,
        lifecycle: elem.properties['Lifecycle status'] ?? elem.properties['Status'] ?? 'unknown',
        businessFunctions: servedFunctions.map(fId => model.elements[fId]?.name).filter(Boolean),
      });
    }
  }

  return results;
}

/**
 * Find all integration interfaces for a given application.
 * Used by Lena (Integration) in Step 0.
 */
export function findInterfaces(model, applicationId) {
  const interfaces = [];

  for (const rel of model.relationships) {
    if (rel.type !== 'Serving' && rel.type !== 'Flow' && rel.type !== 'Access') continue;

    const isSource = rel.source === applicationId;
    const isTarget = rel.target === applicationId;

    if (!isSource && !isTarget) continue;

    const otherId = isSource ? rel.target : rel.source;
    const other = model.elements[otherId];
    if (!other) continue;

    interfaces.push({
      direction: isSource ? 'outbound' : 'inbound',
      type: rel.type,
      otherId,
      otherName: other.name,
      otherType: other.type,
    });
  }

  return interfaces;
}

/**
 * Find cascade dependencies — what's downstream from a system.
 * Used by Lena (Integration) and Jan (Infrastructure) for blast radius analysis.
 * Multi-hop traversal (2-3 levels by default).
 */
export function findCascadeDependencies(model, applicationId, maxHops = 3) {
  const visited = new Set([applicationId]);
  const result = { direct: [], indirect: [] };

  let frontier = [applicationId];
  let hop = 0;

  while (frontier.length > 0 && hop < maxHops) {
    hop++;
    const nextFrontier = [];

    for (const id of frontier) {
      for (const rel of model.relationships) {
        if (rel.source !== id) continue;
        if (visited.has(rel.target)) continue;
        if (!['Serving', 'Flow', 'Triggering', 'Access'].includes(rel.type)) continue;

        const target = model.elements[rel.target];
        if (!target) continue;

        visited.add(rel.target);
        nextFrontier.push(rel.target);

        const entry = {
          id: rel.target,
          name: target.name,
          type: target.type,
          layer: target.layer,
          relationship: rel.type,
          hop,
        };

        if (hop === 1) result.direct.push(entry);
        else result.indirect.push(entry);
      }
    }

    frontier = nextFrontier;
  }

  return result;
}

/**
 * Find all data objects accessed by an application.
 * Used by Aisha (Data) in Step 0 for data classification.
 */
export function findDataObjects(model, applicationId) {
  const dataObjects = [];

  for (const rel of model.relationships) {
    if (rel.source !== applicationId && rel.target !== applicationId) continue;
    if (rel.type !== 'Access' && rel.type !== 'Flow') continue;

    const otherId = rel.source === applicationId ? rel.target : rel.source;
    const other = model.elements[otherId];
    if (!other || other.type !== 'DataObject') continue;

    dataObjects.push({
      id: other.id,
      name: other.name,
      accessType: rel.source === applicationId ? 'write' : 'read',
      classification: other.properties['Classification'] ?? other.properties['Classificatie'] ?? 'unknown',
    });
  }

  return dataObjects;
}

// ---------------------------------------------------------------------------
// STRIDE pre-fill — generate threat model from actual model components
// Victor's killer feature: a STRIDE model that already knows the attack surface
// ---------------------------------------------------------------------------

/**
 * Generate a STRIDE threat model pre-filled with actual components from the model.
 * Each STRIDE category gets entries based on what actually exists in the landscape.
 */
export function generateSTRIDEPrefill(model, applicationId) {
  const app = model.elements[applicationId];
  if (!app) return null;

  const interfaces = findInterfaces(model, applicationId);
  const dataObjects = findDataObjects(model, applicationId);
  const cascade = findCascadeDependencies(model, applicationId, 1);

  const threats = {
    Spoofing: [],
    Tampering: [],
    Repudiation: [],
    InformationDisclosure: [],
    DenialOfService: [],
    ElevationOfPrivilege: [],
  };

  // Spoofing — every interface is a potential spoofing target
  for (const iface of interfaces) {
    threats.Spoofing.push({
      component: `${app.name} → ${iface.otherName} (${iface.direction} ${iface.type})`,
      finding: `${iface.direction === 'inbound' ? 'Incoming' : 'Outgoing'} ${iface.type} relationship with ${iface.otherName} — verify authentication`,
      risk: iface.type === 'Flow' ? 'H' : 'M',
      mitigation: `Verify authentication mechanism for ${iface.direction} ${iface.type} to ${iface.otherName}`,
    });
  }

  // Tampering — data objects without integrity controls
  for (const dof of dataObjects) {
    threats.Tampering.push({
      component: dof.name,
      finding: `Application has ${dof.accessType} access to ${dof.name} (classification: ${dof.classification})`,
      risk: ['bijzondere persoonsgegevens', 'confidential', 'geheim'].includes(dof.classification.toLowerCase()) ? 'H' : 'M',
      mitigation: `Implement integrity controls for ${dof.accessType} access to ${dof.name}`,
    });
  }

  // Repudiation — all data access should be logged (NEN 7513)
  if (dataObjects.some(d => d.classification.toLowerCase().includes('persoon') || d.classification.toLowerCase().includes('patient'))) {
    threats.Repudiation.push({
      component: `${app.name} data access`,
      finding: 'Application accesses personal/patient data — NEN 7513 audit logging required',
      risk: 'H',
      mitigation: 'Implement NEN 7513 compliant audit logging for all data access events',
    });
  }

  // Information Disclosure — data objects with classification concerns
  const sensitiveData = dataObjects.filter(d =>
    ['bijzondere persoonsgegevens', 'persoonsgegevens', 'confidential', 'geheim'].includes(d.classification.toLowerCase())
  );
  if (sensitiveData.length > 0) {
    threats.InformationDisclosure.push({
      component: `${app.name} data handling`,
      finding: `Application handles ${sensitiveData.length} sensitive data object(s): ${sensitiveData.map(d => d.name).join(', ')}`,
      risk: 'H',
      mitigation: 'Verify encryption at rest and in transit for all sensitive data',
    });
  }

  // Denial of Service — downstream dependents
  if (cascade.direct.length > 0) {
    threats.DenialOfService.push({
      component: `${app.name} availability`,
      finding: `${cascade.direct.length} downstream system(s) depend on this application: ${cascade.direct.map(d => d.name).join(', ')}`,
      risk: cascade.direct.some(d => d.type === 'ApplicationComponent') ? 'H' : 'M',
      mitigation: 'Implement rate limiting, health checks, and circuit breakers for downstream consumers',
    });
  }

  // Elevation of Privilege — role model assessment
  threats.ElevationOfPrivilege.push({
    component: `${app.name} authorization`,
    finding: 'Role model and privilege separation to be reviewed — verify least-privilege access',
    risk: 'M',
    mitigation: 'Implement RBAC with least-privilege roles. Verify no shared service accounts with elevated privileges.',
  });

  return {
    application: { id: applicationId, name: app.name },
    interfaceCount: interfaces.length,
    dataObjectCount: dataObjects.length,
    downstreamCount: cascade.direct.length,
    threats,
    generatedAt: new Date().toISOString(),
    draft: true,
  };
}

// ---------------------------------------------------------------------------
// ZiRA conflict detection — "what should exist" vs "what actually exists"
// ---------------------------------------------------------------------------

/**
 * Compare hospital's Archi model against ZiRA reference model.
 * Surfaces conflicts: ZiRA says X should serve Y, but hospital has Z serving Y.
 */
export function detectZiRAConflicts(hospitalModel, ziraModel) {
  const conflicts = [];

  // Build a map of which application functions serve which business functions in each model
  const hospitalServing = buildServingMap(hospitalModel);
  const ziraServing = buildServingMap(ziraModel);

  // Check each ZiRA business function
  for (const [bfId, bfData] of Object.entries(ziraServing)) {
    const hospitalApps = hospitalServing[bfId];
    const ziraApps = ziraServing[bfId];

    if (!ziraApps) continue; // Not in ZiRA — hospital-specific

    if (!hospitalApps && ziraApps) {
      conflicts.push({
        type: 'missing',
        businessFunction: bfData.name,
        ziRAExpects: ziraApps.map(a => a.name).join(', '),
        hospitalHas: 'nothing',
        message: `ZiRA expects business function "${bfData.name}" to be served by ${ziraApps.map(a => a.name).join(', ')}. No implementation found in hospital model.`,
      });
    } else if (hospitalApps && ziraApps) {
      // Check if the serving applications match
      const hospitalNames = new Set(hospitalApps.map(a => a.name.toLowerCase()));
      const ziraNames = new Set(ziraApps.map(a => a.name.toLowerCase()));

      const mismatches = hospitalApps.filter(a => !ziraNames.has(a.name.toLowerCase()));
      if (mismatches.length > 0) {
        conflicts.push({
          type: 'mismatch',
          businessFunction: bfData.name,
          ziRAExpects: ziraApps.map(a => a.name).join(', '),
          hospitalHas: hospitalApps.map(a => a.name).join(', '),
          message: `ZiRA says "${bfData.name}" should be served by ${ziraApps.map(a => a.name).join(', ')}. Hospital model shows ${hospitalApps.map(a => a.name).join(', ')}.`,
        });
      }
    }
  }

  return conflicts;
}

function buildServingMap(model) {
  const serving = {};

  for (const rel of model.relationships) {
    if (rel.type !== 'Serving' && rel.type !== 'Realization') continue;

    const source = model.elements[rel.source];
    const target = model.elements[rel.target];

    if (!source || !target) continue;

    // Application functions serving business functions
    if (target.type === 'BusinessFunction' && source.layer === 'Application') {
      if (!serving[rel.target]) {
        serving[rel.target] = { name: target.name, apps: [] };
      }
      serving[rel.target].apps.push({ id: source.id, name: source.name });
    }
  }

  // Flatten to just name → apps
  const result = {};
  for (const [key, val] of Object.entries(serving)) {
    result[key] = val;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Landscape context builder — feeds Step 0 output
// ---------------------------------------------------------------------------

/**
 * Build a landscape context brief from the Archi model for a given proposal.
 * This is the core Step 0 output that gets injected into persona history.
 */
export function buildLandscapeContext(model, proposalKeywords) {
  const existingApps = findApplicationsByCapability(model, proposalKeywords);
  const allAppNames = existingApps.map(a => a.name);

  const interfaces = [];
  const dataObjects = [];
  const cascadeDeps = [];

  for (const app of existingApps) {
    const appInterfaces = findInterfaces(model, app.id);
    const appDataObjects = findDataObjects(model, app.id);
    const appCascade = findCascadeDependencies(model, app.id, 2);

    interfaces.push(...appInterfaces.map(i => ({
      from: app.name,
      to: i.otherName,
      direction: i.direction,
      type: i.type,
    })));

    dataObjects.push(...appDataObjects.map(d => ({
      heldBy: app.name,
      name: d.name,
      accessType: d.accessType,
      classification: d.classification,
    })));

    cascadeDeps.push(...appCascade.direct.map(d => ({
      source: app.name,
      target: d.name,
      relationship: d.relationship,
    })));
  }

  return {
    existingApps: allAppNames,
    relatedInterfaces: [...new Set(interfaces.map(i => `${i.from} →${i.type}→ ${i.to}`))],
    openRisks: dataObjects
      .filter(d => ['bijzondere persoonsgegevens', 'persoonsgegevens'].includes(d.classification.toLowerCase()))
      .map(d => `Sensitive data (${d.classification}): ${d.name} accessed by ${d.heldBy}`),
    recentChanges: [],
    techRadarStatus: existingApps.map(a => `${a.name}: ${a.lifecycle}`).join(', ') || 'unknown',
    capabilityMap: existingApps.map(a => `${a.name} → ${a.businessFunctions.join(', ')}`).join('; ') || 'not found',
    raw: { existingApps, interfaces: interfaces.slice(0, 20), dataObjects, cascadeDeps: cascadeDeps.slice(0, 15) },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getRelatedTargets(model, elementId, relType) {
  return model.relationships
    .filter(r => r.source === elementId && r.type === relType)
    .map(r => r.target);
}