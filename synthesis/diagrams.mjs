/**
 * synthesis/diagrams.mjs — ArchiMate diagram generation for draw.io
 *
 * Generates structured diagram data from assessment context.
 * Output is draw.io XML that can be opened directly or sent via MCP.
 *
 * Principles:
 *   1. Diagrams are generated from structured data (persona findings, ZiRA mappings),
 *      never from parsing prose
 *   2. Each diagram type has a deterministic layout algorithm
 *   3. ArchiMate notation uses draw.io's built-in shape library
 *   4. Generated diagrams are DRAFTS — human rearranges in draw.io
 *   5. The draw.io MCP (@drawio/mcp or drawio-mcp-server) handles file creation
 */

// ---------------------------------------------------------------------------
// ArchiMate element types → draw.io shapes
// ---------------------------------------------------------------------------

const ARCHIMATE_SHAPES = {
  // Business layer
  BusinessActor: { shape: 'mxgraph.archimate.business.actor', fill: '#FFFFCC', stroke: '#000000' },
  BusinessRole: { shape: 'mxgraph.archimate.business.role', fill: '#FFFFCC', stroke: '#000000' },
  BusinessFunction: { shape: 'mxgraph.archimate.business.function', fill: '#FFFFCC', stroke: '#000000' },
  BusinessProcess: { shape: 'mxgraph.archimate.business.process', fill: '#FFFFCC', stroke: '#000000' },
  BusinessService: { shape: 'mxgraph.archimate.business.service', fill: '#FFFFCC', stroke: '#000000' },

  // Application layer
  ApplicationComponent: { shape: 'mxgraph.archimate.application.component', fill: '#99CCFF', stroke: '#000000' },
  ApplicationFunction: { shape: 'mxgraph.archimate.application.function', fill: '#99CCFF', stroke: '#000000' },
  ApplicationService: { shape: 'mxgraph.archimate.application.service', fill: '#99CCFF', stroke: '#000000' },
  DataObject: { shape: 'mxgraph.archimate.application.dataobject', fill: '#99CCFF', stroke: '#000000' },

  // Technology layer
  Node: { shape: 'mxgraph.archimate.technology.node', fill: '#CCE5FF', stroke: '#000000' },
  SystemSoftware: { shape: 'mxgraph.archimate.technology.systemsoftware', fill: '#CCE5FF', stroke: '#000000' },
  TechnologyService: { shape: 'mxgraph.archimate.technology.service', fill: '#CCE5FF', stroke: '#000000' },

  // Motivation
  Stakeholder: { shape: 'mxgraph.archimate.motivation.stakeholder', fill: '#FFFFFF', stroke: '#000000' },
  Requirement: { shape: 'mxgraph.archimate.motivation.requirement', fill: '#FFFFFF', stroke: '#000000' },
  Principle: { shape: 'mxgraph.archimate.motivation.principle', fill: '#FFFFFF', stroke: '#000000' },

  // Fallback
 DEFAULT: { shape: 'rectangle', fill: '#FFFFFF', stroke: '#000000' },
};

// ArchiMate relationship types
const RELATIONSHIP_STYLES = {
  Serving: { style: 'dashed=0;endArrow=open;endFill=0;', label: 'serves' },
  Access: { style: 'dashed=0;endArrow=open;endFill=0;', label: 'accesses' },
  Flow: { style: 'dashed=0;endArrow=open;endFill=0;', label: 'flow' },
  Triggering: { style: 'dashed=0;endArrow=open;endFill=1;', label: 'triggers' },
  Realization: { style: 'dashed=1;endArrow=open;endFill=0;', label: 'realizes' },
  Assignment: { style: 'dashed=0;endArrow=open;endFill=1;', label: 'assigned to' },
  Aggregation: { style: 'dashed=0;endArrow=diamond;endFill=0;', label: '' },
  Composition: { style: 'dashed=0;endArrow=diamond;endFill=1;', label: '' },
  Association: { style: 'dashed=0;endArrow=open;endFill=0;', label: '' },
  Dependency: { style: 'dashed=1;endArrow=open;endFill=0;', label: 'depends on' },
};

// ---------------------------------------------------------------------------
// Layout engine — simple grid-based layout for deterministic positioning
// ---------------------------------------------------------------------------

const LAYER_CONFIG = {
  Business: { y: 50, color: '#FFFFCC' },
  Application: { y: 300, color: '#99CCFF' },
  Technology: { y: 550, color: '#CCE5FF' },
};

const CELL_WIDTH = 160;
const CELL_HEIGHT = 60;
const CELL_GAP_X = 40;
const CELL_GAP_Y = 30;

class DiagramLayout {
  constructor() {
    this.counters = { Business: 0, Application: 0, Technology: 0, Other: 0 };
  }

  position(layer) {
    const cfg = LAYER_CONFIG[layer] ?? { y: 800, color: '#FFFFFF' };
    const idx = this.counters[layer] ?? 0;
    this.counters[layer] = idx + 1;
    return {
      x: 50 + idx * (CELL_WIDTH + CELL_GAP_X),
      y: cfg.y,
    };
  }
}

// ---------------------------------------------------------------------------
// Diagram data structures
// ---------------------------------------------------------------------------

/**
 * @typedef {object} DiagramElement
 * @property {string} id — unique identifier
 * @property {string} name — display label
 * @property {string} type — ArchiMate element type (e.g., ApplicationComponent)
 * @property {string} layer — Business | Application | Technology
 * @property {object} [metadata] — extra data (ZiRA mapping, BIV, etc.)
 */

/**
 * @typedef {object} DiagramRelationship
 * @property {string} id — unique identifier
 * @property {string} source — source element id
 * @property {string} target — target element id
 * @property {string} type — ArchiMate relationship type
 * @property {string} [label] — optional label
 */

/**
 * @typedef {object} Diagram
 * @property {string} name — diagram title
 * @property {DiagramElement[]} elements
 * @property {DiagramRelationship[]} relationships
 */

// ---------------------------------------------------------------------------
// Diagram generators — one per common viewpoint
// ---------------------------------------------------------------------------

/**
 * Generate Application Landscape diagram from assessment data.
 * Shows existing apps, proposed app, integrations, data objects.
 */
export function generateApplicationLandscape(assessmentData) {
  const { existingApps = [], proposedApp, integrations = [], dataObjects = [] } = assessmentData;
  const elements = [];
  const relationships = [];

  // Proposed application
  if (proposedApp) {
    elements.push({
      id: 'proposed',
      name: proposedApp.name ?? '[Voorgesteld systeem]',
      type: 'ApplicationComponent',
      layer: 'Application',
      metadata: { proposed: true },
    });
  }

  // Existing applications
  for (const app of existingApps) {
    elements.push({
      id: `app_${slug(app.name)}`,
      name: app.name,
      type: 'ApplicationComponent',
      layer: 'Application',
      metadata: { status: app.status, overlap: app.overlap },
    });

    if (proposedApp && app.relation) {
      relationships.push({
        id: `rel_${slug(app.name)}_proposed`,
        source: app.relation === 'replaces' ? `app_${slug(app.name)}` : 'proposed',
        target: app.relation === 'replaces' ? 'proposed' : `app_${slug(app.name)}`,
        type: app.relation === 'replaces' ? 'Flow' : 'Serving',
        label: app.relation,
      });
    }
  }

  // Data objects
  for (const d of dataObjects) {
    elements.push({
      id: `data_${slug(d.name)}`,
      name: d.name,
      type: 'DataObject',
      layer: 'Application',
      metadata: { classification: d.classification },
    });
  }

  // Integration flows
  for (const intf of integrations) {
    relationships.push({
      id: `intf_${slug(intf.source || 'proposed')}_${slug(intf.target || 'proposed')}`,
      source: intf.source ? `app_${slug(intf.source)}` : 'proposed',
      target: intf.target ? `app_${slug(intf.target)}` : 'proposed',
      type: 'Flow',
      label: intf.protocol ?? '',
    });
  }

  return { name: 'Applicatielandschap / Application Landscape', elements, relationships };
}

/**
 * Generate Integration Overview diagram.
 * Shows data flows between systems with protocol labels.
 */
export function generateIntegrationOverview(assessmentData) {
  const { integrations = [], proposedApp } = assessmentData;
  const elements = [];
  const relationships = [];
  const seenApps = new Set();

  const addApp = (name) => {
    const id = `app_${slug(name)}`;
    if (!seenApps.has(id)) {
      seenApps.add(id);
      elements.push({ id, name, type: 'ApplicationComponent', layer: 'Application' });
    }
    return id;
  };

  // Cloverleaf as middleware
  elements.push({ id: 'cloverleaf', name: 'Cloverleaf', type: 'ApplicationService', layer: 'Technology' });

  if (proposedApp) addApp(proposedApp.name ?? '[Nieuw systeem]');

  for (const intf of integrations) {
    const sourceId = addApp(intf.source ?? proposedApp?.name ?? '[Bron]');
    const targetId = addApp(intf.target ?? '[Doel]');

    // Source → Cloverleaf
    relationships.push({
      id: `flow_${sourceId}_clv`,
      source: sourceId,
      target: 'cloverleaf',
      type: 'Flow',
      label: intf.protocolIn ?? intf.protocol ?? '',
    });

    // Cloverleaf → Target
    relationships.push({
      id: `flow_clv_${targetId}`,
      source: 'cloverleaf',
      target: targetId,
      type: 'Flow',
      label: intf.protocolOut ?? '',
    });
  }

  return { name: 'Integratieoverzicht / Integration Overview', elements, relationships };
}

/**
 * Generate BIV Classification diagram.
 * Shows application with BIV scores and derived controls.
 */
export function generateBIVDiagram(assessmentData) {
  const { proposedApp, biv = {} } = assessmentData;
  const elements = [];
  const relationships = [];

  elements.push({
    id: 'proposed',
    name: proposedApp?.name ?? '[Systeem]',
    type: 'ApplicationComponent',
    layer: 'Application',
    metadata: { biv: `B=${biv.B ?? '?'} I=${biv.I ?? '?'} V=${biv.V ?? '?'}` },
  });

  // BIV-driven control requirements
  if (biv.B >= 3) {
    elements.push({ id: 'ctrl_dr', name: 'DR Plan\n(RPO ≤1h, RTO ≤4h)', type: 'Requirement', layer: 'Other' });
    relationships.push({ id: 'rel_dr', source: 'proposed', target: 'ctrl_dr', type: 'Realization' });
  }
  if (biv.I >= 3) {
    elements.push({ id: 'ctrl_val', name: 'Data validatie\nverplicht', type: 'Requirement', layer: 'Other' });
    relationships.push({ id: 'rel_val', source: 'proposed', target: 'ctrl_val', type: 'Realization' });
  }
  if (biv.V >= 3) {
    elements.push({ id: 'ctrl_nen', name: 'NEN 7510 volledig\nDPIA + NEN 7513', type: 'Requirement', layer: 'Other' });
    relationships.push({ id: 'rel_nen', source: 'proposed', target: 'ctrl_nen', type: 'Realization' });
  }

  return { name: 'BIV-classificatie / BIV Classification', elements, relationships };
}

/**
 * Generate ZiRA Positioning diagram.
 * Shows where the proposal maps to ZiRA business functions and information domains.
 */
export function generateZiRADIagram(assessmentData) {
  const { zira = {}, proposedApp } = assessmentData;
  const elements = [];
  const relationships = [];

  // Business domain
  if (zira.domain) {
    elements.push({
      id: 'zira_domain',
      name: zira.domain,
      type: 'BusinessFunction',
      layer: 'Business',
    });
  }

  // Business functions
  for (const bf of (zira.businessFunctions ?? [])) {
    elements.push({
      id: `bf_${slug(bf.name)}`,
      name: bf.name,
      type: 'BusinessFunction',
      layer: 'Business',
    });
    if (zira.domain) {
      relationships.push({
        id: `rel_bf_${slug(bf.name)}`,
        source: `bf_${slug(bf.name)}`,
        target: 'zira_domain',
        type: 'Composition',
      });
    }
  }

  // Proposed application
  if (proposedApp) {
    elements.push({
      id: 'proposed',
      name: proposedApp.name ?? '[Voorgesteld systeem]',
      type: 'ApplicationComponent',
      layer: 'Application',
    });

    // Link to business functions it serves
    for (const bf of (zira.businessFunctions ?? [])) {
      relationships.push({
        id: `rel_proposed_bf_${slug(bf.name)}`,
        source: 'proposed',
        target: `bf_${slug(bf.name)}`,
        type: 'Serving',
      });
    }
  }

  // Information domains
  for (const id of (zira.informationDomains ?? [])) {
    elements.push({
      id: `info_${slug(id.name)}`,
      name: id.name,
      type: 'DataObject',
      layer: 'Application',
    });
  }

  return { name: 'ZiRA-positionering / ZiRA Positioning', elements, relationships };
}

// ---------------------------------------------------------------------------
// draw.io XML generation
// ---------------------------------------------------------------------------

const ELEMENT_ID_COUNTER = { v: 0 };

function nextId() {
  ELEMENT_ID_COUNTER.v += 1;
  return `elem_${ELEMENT_ID_COUNTER.v}`;
}

/**
 * Convert a Diagram object to draw.io XML format.
 * This XML can be opened directly in draw.io or sent via the MCP.
 */
export function diagramToDrawIOXml(diagram) {
  const layout = new DiagramLayout();
  const positions = new Map();
  const xmlParts = [];

  // Root XML
  xmlParts.push('<mxfile><diagram name="' + escapeXml(diagram.name) + '">');
  xmlParts.push('<mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1200" math="0" shadow="0">');
  xmlParts.push('<root>');
  xmlParts.push('<mxCell id="0"/>');
  xmlParts.push('<mxCell id="1" parent="0"/>');

  // Layer headers
  for (const [layer, cfg] of Object.entries(LAYER_CONFIG)) {
    const layerId = `layer_${layer}`;
    xmlParts.push(`<mxCell id="${layerId}" value="${layer} Layer" style="swimlane;startSize=30;fillColor=${cfg.color};strokeColor=#000000;" vertex="1" parent="1">`);
    xmlParts.push(`<mxGeometry x="10" y="${cfg.y - 30}" width="1500" height="220" as="geometry"/>`);
    xmlParts.push('</mxCell>');
  }

  // Elements
  for (const elem of diagram.elements) {
    const cellId = nextId();
    positions.set(elem.id, cellId);
    const pos = layout.position(elem.layer ?? 'Application');
    const shapeConfig = ARCHIMATE_SHAPES[elem.type] ?? ARCHIMATE_SHAPES.DEFAULT;

    const style = `shape=${shapeConfig.shape};fillColor=${shapeConfig.fill};strokeColor=${shapeConfig.stroke};fontStyle=1;fontSize=12;`;
    const bivLabel = elem.metadata?.biv ? `\n[${elem.metadata.biv}]` : '';

    xmlParts.push(`<mxCell id="${cellId}" value="${escapeXml(elem.name)}${bivLabel}" style="${style}" vertex="1" parent="1">`);
    xmlParts.push(`<mxGeometry x="${pos.x}" y="${pos.y}" width="${CELL_WIDTH}" height="${CELL_HEIGHT}" as="geometry"/>`);
    xmlParts.push('</mxCell>');
  }

  // Relationships
  for (const rel of diagram.relationships) {
    const sourceCellId = positions.get(rel.source);
    const targetCellId = positions.get(rel.target);
    if (!sourceCellId || !targetCellId) continue;

    const relStyle = RELATIONSHIP_STYLES[rel.type] ?? RELATIONSHIP_STYLES.Association;
    const cellId = nextId();

    xmlParts.push(`<mxCell id="${cellId}" value="${escapeXml(rel.label ?? '')}" style="${relStyle.style}" edge="1" source="${sourceCellId}" target="${targetCellId}" parent="1">`);
    xmlParts.push('<mxGeometry relative="1" as="geometry"/>');
    xmlParts.push('</mxCell>');
  }

  xmlParts.push('</root></mxGraphModel></diagram></mxfile>');
  return xmlParts.join('');
}

/**
 * Convert a Diagram to Mermaid syntax (lighter weight, also supported by draw.io MCP).
 */
export function diagramToMermaid(diagram) {
  const lines = ['graph TD'];

  for (const elem of diagram.elements) {
    const safeId = mermaidId(elem.id);
    lines.push(`    ${safeId}["${elem.name}"]`);
  }

  for (const rel of diagram.relationships) {
    const source = mermaidId(rel.source);
    const target = mermaidId(rel.target);
    const label = rel.label ? `|${rel.label}|` : '';
    const arrow = ['Realization', 'Dependency'].includes(rel.type) ? '-.->' : '-->';
    lines.push(`    ${source} ${arrow} ${label} ${target}`);
  }

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Master diagram generator — picks the right diagram(s) for an assessment
// ---------------------------------------------------------------------------

/**
 * Generate all applicable diagrams from assessment data.
 *
 * @param {object} assessmentData — structured assessment output
 * @returns {object} — { diagramName: { xml, mermaid } }
 */
export function generateDiagrams(assessmentData) {
  const { requestType, ratings = {} } = assessmentData;
  const diagrams = {};

  // Always generate landscape
  diagrams['application-landscape'] = {
    xml: diagramToDrawIOXml(generateApplicationLandscape(assessmentData)),
    mermaid: diagramToMermaid(generateApplicationLandscape(assessmentData)),
  };

  // Integration overview if integrations exist
  if (assessmentData.integrations?.length || requestType === 'integration') {
    diagrams['integration-overview'] = {
      xml: diagramToDrawIOXml(generateIntegrationOverview(assessmentData)),
      mermaid: diagramToMermaid(generateIntegrationOverview(assessmentData)),
    };
  }

  // BIV diagram if BIV is set
  if (assessmentData.biv) {
    diagrams['biv-classification'] = {
      xml: diagramToDrawIOXml(generateBIVDiagram(assessmentData)),
      mermaid: diagramToMermaid(generateBIVDiagram(assessmentData)),
    };
  }

  // ZiRA positioning if ZiRA data exists
  if (assessmentData.zira) {
    diagrams['zira-positioning'] = {
      xml: diagramToDrawIOXml(generateZiRADIagram(assessmentData)),
      mermaid: diagramToMermaid(generateZiRADIagram(assessmentData)),
    };
  }

  return diagrams;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function slug(name) {
  return String(name).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

function escapeXml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function mermaidId(id) {
  return id.replace(/[^a-zA-Z0-9]/g, '_');
}