/**
 * synthesis/pipeline.mjs — Full Preflight pipeline orchestration.
 *
 * Orchestrates the six-step pipeline from request to board-ready output.
 * This is the top-level module that ties together personas, synthesis, diagrams,
 * citations, conditions, and the request lifecycle.
 *
 * Principles:
 *   1. All authority outputs are DRAFTS requiring human sign-off
 *   2. Every claim must cite its source (persona or knowledge chunk)
 *   3. Every generated document includes an accountability disclaimer
 *   4. Deduplication merges overlapping persona findings
 *   5. Triage floors prevent dangerous shortcuts
 *   6. The lifecycle is a state machine — no skipping steps
 */

import {
  PERSONAS, PERSPECTIVES, selectRelevant, injectLandscapeContext,
  parseAssessmentRatings, determineTriageLevel, RATING_SCALE,
} from '../personas/ea-council-personas.mjs';
import {
  buildContext, generateAllDocuments, determineRequiredDocuments,
  formatPersonaFindings, generateRiskRegister, generateConditionsTable,
  generateCitationAppendix, citationConstraintPrompt, verifyCitations,
  citePersona, citeKnowledge,
} from './engine.mjs';
import { generateDiagrams } from './diagrams.mjs';

// ---------------------------------------------------------------------------
// Request lifecycle — state machine
// ---------------------------------------------------------------------------

export const LIFECYCLE_STATES = [
  'SUBMITTED',       // Business request received
  'PRELIMINARY',     // Step 0-1: Ingest & classify
  'CLARIFICATION',   // Missing context — architect needs to answer questions
  'ASSESSED',        // Steps 2-4: Assessment complete, draft products generated
  'BOARD_READY',     // Architect reviewed and approved draft
  'IN_REVIEW',       // Board meeting scheduled
  'DECIDED',         // Board recorded decision
  'CONDITIONS_OPEN',  // Approved with conditions — tracking open conditions
  'CLOSED',          // All conditions met or request withdrawn
];

const VALID_TRANSITIONS = {
  SUBMITTED: ['PRELIMINARY'],
  PRELIMINARY: ['CLARIFICATION', 'ASSESSED'],
  CLARIFICATION: ['PRELIMINARY', 'ASSESSED'],
  ASSESSED: ['BOARD_READY', 'CLARIFICATION'],
  BOARD_READY: ['IN_REVIEW', 'ASSESSED'],
  IN_REVIEW: ['DECIDED'],
  DECIDED: ['CONDITIONS_OPEN', 'CLOSED'],
  CONDITIONS_OPEN: ['CONDITIONS_OPEN', 'CLOSED'],
  CLOSED: [],
};

/**
 * Check if a state transition is valid.
 */
export function canTransition(from, to) {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

/**
 * Create a new assessment request.
 */
export function createRequest({ description, submittedBy, attachments = [] }) {
  return {
    id: `REQ-${Date.now().toString(36)}`,
    state: 'SUBMITTED',
    submittedAt: new Date().toISOString(),
    submittedBy,
    description,
    attachments,
    requestType: null,
    impactLevel: null,
    ratings: {},
    personaFindings: [],
    triage: null,
    biv: null,
    zira: null,
    landscape: null,
    conditions: [],
    decisions: [],
    documents: {},
    diagrams: {},
    lifecycle: [{ state: 'SUBMITTED', at: new Date().toISOString(), by: submittedBy }],
  };
}

// ---------------------------------------------------------------------------
// Triage floors — hard rules that prevent dangerous shortcuts
// ---------------------------------------------------------------------------

const TRIAGE_FLOORS = {
  'clinical-system': {
    minTreatment: 'standard-review',
    alwaysActive: ['cmio', 'fg-dpo', 'po'],
    message: 'Clinical system proposals cannot be fast-tracked. CMIO and FG-DPO are always active.',
  },
  'patient-data': {
    minTreatment: 'standard-review',
    alwaysActive: ['fg-dpo', 'po'],
    message: 'Proposals involving patient data always require FG-DPO assessment.',
  },
  'manufacturing-ot': {
    minTreatment: 'standard-review',
    alwaysActive: ['manufacturing'],
    conditions: ['ot-boundary-detected'],
    message: 'IT/OT boundary proposals require Manufacturing & OT assessment.',
  },
};

/**
 * Apply triage floors to a request.
 * Ensures minimum treatment levels and mandatory persona activation.
 */
export function applyTriageFloors(requestType, impactLevel, selectedPerspectives, triage) {
  const floor = TRIAGE_FLOORS[requestType];
  let adjustedPerspectives = [...selectedPerspectives];
  let adjustedTriage = { ...triage };

  if (floor) {
    // Ensure always-active personas are included
    for (const pid of floor.alwaysActive) {
      if (!adjustedPerspectives.includes(pid)) {
        adjustedPerspectives.push(pid);
      }
    }

    // Floor the treatment level
    if (triage.treatment === 'fast-track') {
      adjustedTriage = {
        ...triage,
        treatment: floor.minTreatment,
        reason: `${floor.message} (triage floor)`,
      };
    }
  }

  // Critical impact always gets deep review + red team
  if (impactLevel === 'critical') {
    adjustedTriage = {
      ...adjustedTriage,
      treatment: 'deep-review',
      reason: adjustedTriage.reason
        ? `${adjustedTriage.reason}; critical impact requires deep review`
        : 'Critical impact requires deep review with Red Team',
    };
    if (!adjustedPerspectives.includes('redteam')) {
      adjustedPerspectives.push('redteam');
    }
  }

  // High impact gets red team
  if (impactLevel === 'high' && !adjustedPerspectives.includes('redteam')) {
    adjustedPerspectives.push('redteam');
  }

  return { perspectives: adjustedPerspectives, triage: adjustedTriage };
}

// ---------------------------------------------------------------------------
// Authority sign-off — all authority outputs are DRAFTS
// ---------------------------------------------------------------------------

const AUTHORITY_TYPES = {
  VETO: { persona: 'Victor', label: 'Security Veto', requiresSignOff: 'security-architect' },
  ESCALATION: { persona: 'Nadia', label: 'Risk Escalation', requiresSignOff: 'compliance-officer' },
  INDEPENDENT: { persona: 'FG-DPO', label: 'FG Determination', requiresSignOff: 'fg-dpo' },
  PATIENT_SAFETY: { persona: 'CMIO', label: 'Patient Safety Floor', requiresSignOff: 'cmio' },
};

/**
 * Process authority actions from persona findings.
 * Returns authority decisions with sign-off requirements.
 */
export function processAuthorityActions(personaFindings) {
  const actions = [];

  for (const pf of personaFindings) {
    if (!pf.authority || pf.authority === 'CHALLENGE') continue;

    const authority = AUTHORITY_TYPES[pf.authority];
    if (!authority) continue;

    actions.push({
      type: pf.authority,
      persona: authority.persona,
      label: authority.label,
      triggered: pf.rating === 'block',
      requiresSignOff: authority.requiresSignOff,
      signOffStatus: 'PENDING',
      findings: pf.findings ?? [],
      conditions: pf.conditions ?? [],
      draftDisclaimer: `This is a DRAFT ${authority.label} assessment generated by Preflight. ` +
        `The ${authority.requiresSignOff.replace(/-/g, ' ')} must review and sign off before this becomes binding.`,
    });
  }

  return actions;
}

// ---------------------------------------------------------------------------
// Condition lifecycle — auto-created from persona assessments
// ---------------------------------------------------------------------------

/**
 * Create conditions from persona findings.
 * Each condition from a conditional/block rating becomes a trackable item.
 */
export function createConditions(personaFindings, assessmentId) {
  const conditions = [];
  let idx = 1;

  for (const pf of personaFindings) {
    if (!pf.conditions?.length) continue;
    for (const cond of pf.conditions) {
      conditions.push({
        id: `${assessmentId}-C${idx}`,
        condition: cond,
        sourcePersona: pf.name,
        sourceRole: pf.role,
        owner: null, // to be assigned by architect
        dueDate: null,
        status: 'OPEN',
        evidence: null,
        createdAt: new Date().toISOString(),
      });
      idx++;
    }
  }

  return conditions;
}

/**
 * Check if all conditions for an assessment are met.
 */
export function allConditionsMet(conditions) {
  return conditions.every(c => c.status === 'MET');
}

// ---------------------------------------------------------------------------
// BIV scoring — aggregated from persona inputs
// ---------------------------------------------------------------------------

/**
 * Determine BIV classification from persona findings.
 * The highest score per dimension wins (conservative).
 * Each dimension is scored 1-3 (low/medium/high).
 */
export function determineBIV(personaFindings, requestType) {
  // Default: medium unless elevated
  let B = 2, I = 2, V = 2;

  // Automatic elevation rules based on request type and persona findings
  const isClinical = requestType === 'clinical-system';
  const hasPatientData = ['patient-data', 'clinical-system'].includes(requestType);

  if (isClinical) B = 3; // Clinical system = maximum availability requirement
  if (hasPatientData) { I = 3; V = 3; } // Patient data = max integrity + confidentiality

  // Persona-driven overrides
  for (const pf of personaFindings) {
    if (pf.biv) {
      B = Math.max(B, pf.biv.B ?? 0);
      I = Math.max(I, pf.biv.I ?? 0);
      V = Math.max(V, pf.biv.V ?? 0);
    }
  }

  const rpo = B === 3 ? '≤1 uur' : B === 2 ? '≤4 uur' : '≤24 uur';
  const rto = B === 3 ? '≤4 uur' : B === 2 ? '≤8 uur' : '≤24 uur';

  return { B, I, V, rpo, rto };
}

// ---------------------------------------------------------------------------
// ZiRA principetoets — 12 principles evaluation
// ---------------------------------------------------------------------------

const ZIRA_PRINCIPLES = [
  { num: 1, name: 'Waardevol', desc: 'Waarde toevoegen, aansluiten bij organisatiedoelen', weight: 'highest' },
  { num: 2, name: 'Veilig en vertrouwd', desc: 'Veiligheid en privacy voorop' },
  { num: 3, name: 'Duurzaam', desc: 'Toekomstbestendig, verspilling vermijden' },
  { num: 4, name: 'Continu', desc: 'Continuiteit van zorg borgen' },
  { num: 5, name: 'Mens centraal', desc: 'De mens staat centraal' },
  { num: 6, name: 'Samen', desc: 'Afstemming met stakeholders' },
  { num: 7, name: 'Gestandaardiseerd', desc: 'Open standaarden en best practices' },
  { num: 8, name: 'Flexibel', desc: 'Modulair, uitbreidbaar, vervangbaar' },
  { num: 9, name: 'Eenvoudig', desc: 'Eenvoudigste oplossing die aan eisen voldoet' },
  { num: 10, name: 'Onder eigenaarschap', desc: 'Aangewezen eigenaren' },
  { num: 11, name: 'Datagedreven', desc: 'Gestructureerd voor hergebruik' },
  { num: 12, name: 'Innovatief', desc: 'Innovatie actief nastreven' },
];

/**
 * Generate principetoets from persona findings.
 * Each principle gets a rating based on which personas raised concerns.
 */
export function generatePrincipetoets(personaFindings) {
  const rows = [];
  let satisfied = 0, partial = 0, unsatisfied = 0, na = 0;

  // Map persona concerns to principles
  const principleAssessments = mapFindingsToPrinciples(personaFindings);

  for (const principle of ZIRA_PRINCIPLES) {
    const assessment = principleAssessments[principle.num] ?? 'N.v.t.';
    const toelichting = getPrincipeToelichting(principle.num, personaFindings);

    if (assessment === 'Voldoet') satisfied++;
    else if (assessment === 'Deels') partial++;
    else if (assessment === 'Niet') unsatisfied++;
    else na++;

    rows.push(
      `| ${principle.num} | **${principle.name}** — ${principle.desc} | ${assessment} | ${toelichting} |`
    );
  }

  const summary = `${satisfied} van 12 voldoet, ${partial} deels, ${unsatisfied} niet`;

  return {
    table: `| # | Principe | Beoordeling | Toelichting |\n|---|----------|-------------|-------------|\n${rows.join('\n')}`,
    summary,
    satisfied,
    partial,
    unsatisfied,
    na,
  };
}

function mapFindingsToPrinciples(personaFindings) {
  // Heuristic mapping from persona domain to ZiRA principles
  const assessments = {};

  for (const pf of personaFindings) {
    if (pf.rating === 'block') {
      // Blocks map to specific principle failures
      if (pf.name === 'Victor') { assessments[2] = 'Niet'; }
      if (pf.name === 'Nadia') { assessments[2] = 'Niet'; }
      if (pf.name === 'FG-DPO') { assessments[2] = 'Niet'; }
    }
    if (pf.rating === 'concern') {
      if (pf.name === 'Victor') { assessments[2] = assessments[2] ?? 'Deels'; }
      if (pf.name === 'Nadia') { assessments[2] = assessments[2] ?? 'Deels'; }
      if (pf.name === 'Jan') { assessments[4] = 'Deels'; }
      if (pf.name === 'Lena') { assessments[8] = assessments[8] ?? 'Deels'; }
      if (pf.name === 'Sophie') { assessments[1] = assessments[1] ?? 'Deels'; }
      if (pf.name === 'Thomas') { assessments[7] = assessments[7] ?? 'Deels'; assessments[8] = assessments[8] ?? 'Deels'; }
      if (pf.name === 'Marcus') { assessments[8] = assessments[8] ?? 'Deels'; assessments[9] = assessments[9] ?? 'Deels'; }
    }
  }

  return assessments;
}

function getPrincipeToelichting(num, personaFindings) {
  const relevant = personaFindings.filter(pf => {
    const pMap = { 2: ['Victor', 'Nadia', 'FG-DPO', 'PO', 'CISO', 'ISO-Officer'], 4: ['Jan', 'CMIO'], 8: ['Lena', 'Thomas', 'Marcus'], 9: ['Marcus', 'Thomas'], 1: ['Sophie', 'CIO'], 7: ['Thomas'] };
    return pMap[num]?.includes(pf.name);
  });

  if (!relevant.length) return '[te beoordelen door architect]';
  return relevant.map(pf => `${pf.name}: ${pf.findings?.[0] ?? pf.rating}`).join('; ');
}

// ---------------------------------------------------------------------------
// Deduplication — merge overlapping findings from multiple personas
// ---------------------------------------------------------------------------

/**
 * Deduplicate persona findings across different personas.
 * When 3+ personas raise the same concern, merge into a shared consensus
 * and preserve unique per-persona findings separately.
 */
export function deduplicateFindings(personaFindings) {
  const findingCounts = new Map(); // normalized text → [{ persona, finding }]

  for (const pf of personaFindings) {
    if (pf.rating === 'approve' || pf.rating === 'na') continue;
    for (const finding of (pf.findings ?? [])) {
      const key = normalizeFinding(finding);
      if (!findingCounts.has(key)) findingCounts.set(key, []);
      findingCounts.get(key).push({ name: pf.name, role: pf.role, original: finding });
    }
  }

  const consensus = []; // findings raised by 3+ personas
  const unique = [];    // per-persona unique findings

  for (const [key, sources] of findingCounts) {
    if (sources.length >= 3) {
      consensus.push({
        finding: sources[0].original,
        raisedBy: sources.map(s => s.name),
        count: sources.length,
      });
    } else {
      for (const s of sources) {
        unique.push(s.original);
      }
    }
  }

  return { consensus, unique };
}

function normalizeFinding(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 3)
    .sort()
    .join(' ');
}

// ---------------------------------------------------------------------------
// Accountability disclaimer — appended to every generated document
// ---------------------------------------------------------------------------

export const ACCOUNTABILITY_DISCLAIMER = `
> **Disclaimer:** This is a draft assessment generated by Preflight using AI personas.
> The architect owns the final assessment. The board owns the decision.
> Preflight provides analysis, not judgment. All findings require human verification.
> Citations marked [§P:name] come from persona assessments. Citations marked [§K:id] come from the knowledge base.
> Uncited claims are flagged with [VERIFY] and must be confirmed by the architect.
`.trim();

/**
 * Append accountability disclaimer to a generated document.
 */
export function appendDisclaimer(text) {
  return `${text}\n\n---\n\n${ACCOUNTABILITY_DISCLAIMER}`;
}

// ---------------------------------------------------------------------------
// Full pipeline — from request to board-ready output
// ---------------------------------------------------------------------------

/**
 * Run the full Preflight pipeline.
 *
 * Step 0: Ingest — persona-driven discovery queries
 * Step 1: Classify — request type + impact + triage floors
 * Step 2: Retrieve — per-persona RAG (not yet implemented — needs knowledge store)
 * Step 3: Assess — persona evaluations (provided externally)
 * Step 4: Challenge — authority actions (Victor veto, Nadia escalation, FG determination)
 * Step 5: Output — generate documents, diagrams, conditions
 *
 * @param {object} input
 * @param {string} input.description — the business request
 * @param {string} input.requestType — classified type
 * @param {string} input.impactLevel — low/medium/high/critical
 * @param {Array}  input.personaFindings — from Step 3
 * @param {object} input.zira — ZiRA positioning data
 * @param {object} input.landscape — from Step 0
 * @param {Array}  input.sources — RAG sources for citation
 * @returns {object} complete assessment output
 */
export function runPipeline(input) {
  const {
    description,
    requestType = 'new-application',
    impactLevel = 'medium',
    personaFindings = [],
    zira = {},
    landscape = {},
    sources = [],
  } = input;

  // Step 1: Classify
  const ratings = {};
  for (const pf of personaFindings) {
    const pid = pf.perspectiveId ?? pf.name.toLowerCase().replace(/[^a-z]/g, '');
    ratings[pid] = pf.rating;
  }

  const triage = determineTriageLevel(ratings);
  const floored = applyTriageFloors(requestType, impactLevel, Object.keys(ratings), triage);

  // Step 4: Authority actions
  const authorityActions = processAuthorityActions(personaFindings);

  // BIV
  const biv = determineBIV(personaFindings, requestType);

  // Conditions
  const assessmentId = `PSA-${new Date().toISOString().split('T')[0].replace(/-/g, '')}`;
  const conditions = createConditions(personaFindings, assessmentId);

  // Principetoets
  const principetoets = generatePrincipetoets(personaFindings);

  // Deduplication
  const deduplicated = deduplicateFindings(personaFindings);

  // Step 5: Output — documents
  const context = buildContext({
    proposalName: description,
    requestType,
    ratings: floored.perspectives.reduce((acc, pid) => {
      acc[pid] = ratings[pid] ?? 'na';
      return acc;
    }, {}),
    personaFindings,
    triage: floored.triage,
    zira,
    biv,
    landscape,
  });

  const documents = generateAllDocuments({
    ...input,
    ratings,
    triage: floored.triage,
    biv,
  });

  // Append disclaimer to all documents
  for (const [name, content] of Object.entries(documents)) {
    documents[name] = appendDisclaimer(content);
  }

  // Diagrams
  const diagrams = generateDiagrams({
    requestType,
    ratings,
    proposedApp: { name: description },
    existingApps: landscape.existingApps ?? [],
    integrations: landscape.integrations ?? [],
    dataObjects: landscape.dataObjects ?? [],
    biv,
    zira,
  });

  // Citation appendix
  const citationAppendix = generateCitationAppendix(personaFindings, sources);

  // Citation constraint for LLM synthesis sections
  const llmConstraint = citationConstraintPrompt(personaFindings, sources);

  return {
    id: assessmentId,
    requestType,
    impactLevel,
    triage: floored.triage,
    biv,
    principalFindings: formatPersonaFindings(personaFindings),
    authorityActions,
    conditions,
    principetoets,
    deduplicated,
    documents,
    diagrams,
    lifecycle: [{ state: 'ASSESSED', at: new Date().toISOString() }],
    citationAppendix,
    llmConstraint,
    disclaimer: ACCOUNTABILITY_DISCLAIMER,
  };
}