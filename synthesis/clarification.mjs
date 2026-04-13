/**
 * synthesis/clarification.mjs — Generate missing-context questions per persona.
 *
 * Before a full assessment, Preflight identifies what's missing.
 * Each persona's `constraints` field tells us what they NEED to see.
 * If it's not in the request or landscape, we ask.
 *
 * "The architect's job is judgment. Preflight's job is to make sure
 *  the architect has everything they need to exercise that judgment."
 */

import { PERSONAS } from '../personas/ea-council-personas.mjs';

/**
 * Generate clarification questions for a proposal.
 *
 * Checks each selected persona's constraints against what we know.
 * If required information is missing, generates a targeted question.
 *
 * @param {string} requestDescription — the business request text
 * @param {object} landscape — landscape context from Step 0
 * @param {string[]} selectedPerspectiveIds — which perspectives are active
 * @returns {object[]} — [{ persona, role, question, required }]
 */
export function generateClarificationQuestions(requestDescription, landscape = {}, selectedPerspectiveIds = []) {
  const questions = [];
  const text = (requestDescription ?? '').toLowerCase();
  const selectedPersonas = PERSONAS.filter(p => {
    const PERSPECTIVE_IDS = { CIO:'cio', CMIO:'cmio', Marcus:'chief', Sophie:'business', Joris:'process', Thomas:'application', Lena:'integration', Jan:'infrastructure', Aisha:'data', Erik:'manufacturing', Petra:'rnd', Victor:'security', CISO:'ciso', 'ISO-Officer':'iso-officer', Nadia:'risk', 'FG-DPO':'fg-dpo', Raven:'redteam', PO:'privacy', Marco:'solution', Daan:'information', Ruben:'network', Femke:'portfolio' };
    const pid = PERSPECTIVE_IDS[p.name];
    return pid ? selectedPerspectiveIds.includes(pid) : false;
  });

  // Key information signals to check for
  const signalChecks = [
    { keywords: ['patient', 'patiënt', 'zorg', 'clinical', 'klinisch', 'medisch', 'EPD', 'HIS'], missing: 'Does this involve patient data or clinical systems?', personas: ['CMIO', 'FG-DPO', 'Aisha'] },
    { keywords: ['vendor', 'leverancier', 'SaaS', 'contract', 'AIVG', 'contract'], missing: 'Is this a new vendor/product selection?', personas: ['Thomas', 'Nadia'] },
    { keywords: ['integrat', 'koppel', 'API', 'interface', 'HL7', 'FHIR', 'Cloverleaf'], missing: 'What systems does this need to integrate with?', personas: ['Lena'] },
    { keywords: ['cloud', 'SaaS', 'hosting', 'on-prem', 'datacenter', 'Azure', 'AWS'], missing: 'Where will this system run?', personas: ['Jan'] },
    { keywords: ['data', 'persoonsgegevens', 'gegevens', 'privacy', 'AVG', 'GDPR', 'DPIA'], missing: 'What data does this system process and where does it flow?', personas: ['Aisha', 'FG-DPO', 'PO'] },
    { keywords: ['budget', 'cost', 'kosten', 'investering', 'TCO', 'licentie'], missing: 'What is the budget and total cost of ownership?', personas: ['CIO'] },
    { keywords: ['security', 'beveiliging', 'NEN 7510', 'encryptie', 'authenticatie'], missing: 'What are the security requirements?', personas: ['Victor', 'ISO-Officer'] },
    { keywords: ['compliance', 'regelgeving', 'NIS2', 'MDR', 'IVDR', 'Wegiz'], missing: 'Which regulatory frameworks apply?', personas: ['Nadia'] },
    { keywords: ['productie', 'factory', 'OT', 'SCADA', 'MES', 'IEC 62443'], missing: 'Does this touch the OT/manufacturing network?', personas: ['Erik'] },
    { keywords: ['AI', 'machine learning', 'algoritme', 'model', 'predict'], missing: 'Does this use AI or machine learning?', personas: ['Aisha'] },
  ];

  for (const check of signalChecks) {
    const found = check.keywords.some(kw => text.includes(kw));
    if (!found) {
      const relevantPersonas = selectedPersonas.filter(p => check.personas.includes(p.name));
      if (relevantPersonas.length > 0) {
        questions.push({
          persona: relevantPersonas[0].name,
          role: relevantPersonas[0].role,
          question: check.missing,
          required: true,
          reason: `Information not found in request. ${relevantPersonas[0].name} needs this to assess the proposal.`,
        });
      }
    }
  }

  // Check landscape completeness
  if (!landscape.existingApps?.length) {
    questions.push({
      persona: 'Marcus',
      role: 'Chief Architect',
      question: 'No existing applications found in the capability space. Is the Archi model up to date for this domain?',
      required: true,
      reason: 'Without landscape context, overlap detection and cascade analysis cannot be performed.',
    });
  }

  return questions;
}

// ---------------------------------------------------------------------------
// Delta re-assessment — only re-evaluate affected personas
// ---------------------------------------------------------------------------

/**
 * When a proposal changes after board feedback, determine which personas
 * need to re-assess and which can carry forward their previous assessment.
 *
 * @param {object} previousAssessment — the v1 assessment
 * @param {object} changes — what changed in the proposal (field deltas)
 * @returns {object} — { reAssess: string[], carryForward: string[], reason: string }
 */
export function determineDeltaReassessment(previousAssessment, changes) {
  const changedFields = Object.keys(changes);
  const previousRatings = previousAssessment.ratings ?? {};

  // Map changed fields to affected persona domains
  const fieldPersonaMap = {
    // Technical architecture changes
    'integration': ['Lena', 'Ruben', 'Victor', 'Jan'],
    'infrastructure': ['Jan', 'Ruben', 'Victor'],
    'data': ['Aisha', 'FG-DPO', 'PO'],
    'security': ['Victor', 'CISO', 'ISO-Officer'],
    'application': ['Thomas', 'Lena', 'Jan'],
    'vendor': ['Thomas', 'Nadia', 'Victor'],
    'clinical': ['CMIO', 'FG-DPO', 'PO'],
    'compliance': ['Nadia', 'FG-DPO'],
    'budget': ['CIO'],
    'process': ['Joris', 'CMIO'],
    'architecture': ['Marcus', 'Sophie', 'Femke'],
  };

  const reAssess = new Set();
  const reason = [];

  // Always re-assess the chief architect on any change
  reAssess.add('Marcus');
  reason.push('Chief Architect always reassesses on changes');

  // Always re-assess Raven on any significant change
  reAssess.add('Raven');
  reason.push('Red Team reassesses on any change to check for new failure modes');

  // Map changed fields to personas
  for (const field of changedFields) {
    const affected = fieldPersonaMap[field.toLowerCase()] ?? [];
    for (const persona of affected) {
      reAssess.add(persona);
    }
    if (affected.length > 0) {
      reason.push(`${field} changes affect: ${affected.join(', ')}`);
    }
  }

  // Check if any authority rating was block/conditional — those personas must re-assess
  for (const [pid, rating] of Object.entries(previousRatings)) {
    if (rating === 'block' || rating === 'conditional') {
      const name = pidToName(pid);
      if (name) reAssess.add(name);
    }
  }

  // Carry forward: all personas NOT in reAssess set
  const allPersonas = Object.keys(previousRatings).map(pidToName).filter(Boolean);
  const carryForward = allPersonas.filter(p => !reAssess.has(p));

  return {
    reAssess: [...reAssess],
    carryForward,
    reason: reason.join('; '),
  };
}

function pidToName(pid) {
  const map = { cio:'CIO', cmio:'CMIO', chief:'Marcus', business:'Sophie', process:'Joris', application:'Thomas', integration:'Lena', infrastructure:'Jan', data:'Aisha', manufacturing:'Erik', rnd:'Petra', security:'Victor', ciso:'CISO', 'iso-officer':'ISO-Officer', risk:'Nadia', 'fg-dpo':'FG-DPO', privacy:'PO', solution:'Marco', information:'Daan', network:'Ruben', portfolio:'Femke' };
  return map[pid];
}

// ---------------------------------------------------------------------------
// Verwerkingsregister draft — FG-DPO's killer feature
// ---------------------------------------------------------------------------

/**
 * Auto-generate a draft verwerkingsregister entry when personal data is detected.
 * This is what the FG-DPO reviews and signs off.
 */
export function generateVerwerkingsregisterDraft(input) {
  const {
    proposalName = '[voorstel]',
    processingDescription = '',
    dataCategories = [],
    purpose = '',
    legalBasis = '',
    dataSubjects = [],
    recipients = [],
    retentionPeriod = '',
    datenschutzGaranties = [],
  } = input;

  return {
    proposal: proposalName,
    entry: {
      verwerkingsactiviteit: processingDescription || '[Beschrijving van de verwerkingsactiviteit]',
      doel: purpose || '[Doel van de verwerking]',
      grondslag: legalBasis || '[Verwerkingsgrondslag — AVG artikel 6 lid 1]',
      categorie_betrokkenen: dataSubjects.length ? dataSubjects : ['[Patiënten', 'Medewerkers', 'Bezoekers]'],
      categorie_persoonsgegevens: dataCategories.length ? dataCategories : ['[BSN', 'naam', 'adres', 'medische gegevens]'],
      ontvangers: recipients.length ? recipients : ['[Ontvangers van de gegevens]'],
      bewaartermijn: retentionPeriod || '[Bewaartermijn]',
      doorgifte_derde_landen: '[Nee / Ja — welke landen en welke waarborgen]',
      datenschutz_garanties: datenschutzGaranties.length ? datenschutzGaranties : ['[Encryptie in transit en at rest', 'Toegangsbeperking op basis van rol', 'Audit logging per NEN 7513]'],
    },
    status: 'CONCEPT — FG-bepaling vereist',
    reviewRequired: true,
    reviewer: 'FG-DPO',
    disclaimer: 'Dit is een concept-verwerkingsregisterentry gegenereerd door Preflight. De FG/DPO beoordeelt de rechtmatigheid van de verwerking. Dit is geen vervanging van de FG-bepaling.',
  };
}

// ---------------------------------------------------------------------------
// [ARCHITECT INPUT NEEDED] marker detection
// ---------------------------------------------------------------------------

/**
 * Scan generated text for sections that are still generic or weak.
 * Insert [ARCHITECT INPUT NEEDED] markers where the assessment
 * couldn't produce specific, grounded findings.
 */
export function markArchitectInputNeeded(text) {
  const genericPhrases = [
    /\[voorstel naam\]/gi,
    /\[voorstel\]/gi,
    /\[naam\]/gi,
    /\[datum\]/gi,
    /\[reden\]/gi,
    /\[beschrijving\]/gi,
    /\[toelichting\]/gi,
    /\[mitigerende maatregel\]/gi,
    /\[eigenaar\]/gi,
    /\[RPO\]/gi,
    /\[RTO\]/gi,
    /\[triage\]/gi,
  ];

  let marked = text;
  let markerCount = 0;

  for (const phrase of genericPhrases) {
    marked = marked.replace(phrase, (match) => {
      markerCount++;
      return `${match} <!-- ARCHITECT INPUT NEEDED -->`;
    });
  }

  // Also mark sections that are entirely placeholder
  marked = marked.replace(/\| \[([^\]]+)\] \|/g, (match, content) => {
    if (content.startsWith('[[')) return match; // Already marked
    return `| [⚠ ${content}] |`;
  });

  return { text: marked, markersAdded: markerCount };
}

// ---------------------------------------------------------------------------
// Persona versioning — MDR traceability
// ---------------------------------------------------------------------------

const PERSONA_VERSION = '1.0.0';
const PERSONA_VERSION_DATE = '2025-04-10';

/**
 * Get the current persona version for traceability.
 * Every assessment records which persona version produced each finding.
 */
export function getPersonaVersion() {
  return {
    version: PERSONA_VERSION,
    date: PERSONA_VERSION_DATE,
    personaCount: PERSONAS.length,
    perspectiveCount: 22,
    hash: computePersonaHash(),
  };
}

function computePersonaHash() {
  // Simple hash of persona definitions for version verification
  const crypto = await_import_crypto();
  const data = JSON.stringify(PERSONAS.map(p => ({
    name: p.name,
    role: p.role,
    incentives: p.incentives.substring(0, 50),
    constraints: p.constraints.substring(0, 50),
  })));
  // In production, use proper crypto. For now, a simple checksum.
  let hash = 0;
  for (let i = 0; i < data.length; i++) {
    hash = ((hash << 5) - hash + data.charCodeAt(i)) | 0;
  }
  return `v${PERSONA_VERSION}-${Math.abs(hash).toString(16)}`;
}

// ---------------------------------------------------------------------------
// BIV cascade triggers — derived control requirements from BIV scores
// ---------------------------------------------------------------------------

/**
 * Given BIV scores, derive mandatory control requirements.
 * This is deterministic — no LLM needed.
 */
export function deriveBIVControls(biv) {
  const { B, I, V } = biv;
  const controls = [];

  if (B === 3) {
    controls.push(
      { requirement: 'Disaster Recovery Plan mandatory', standard: 'NEN 7510', reference: 'B=3' },
      { requirement: 'RPO ≤ 1 hour', standard: 'BIA', reference: 'B=3' },
      { requirement: 'RTO ≤ 4 hours', standard: 'BIA', reference: 'B=3' },
      { requirement: 'Active-active or hot-standby architecture', standard: 'Architecture', reference: 'B=3' },
      { requirement: 'Annual DR test with documented results', standard: 'NEN 7510', reference: 'B=3' },
    );
  } else if (B === 2) {
    controls.push(
      { requirement: 'RPO ≤ 4 hours', standard: 'BIA', reference: 'B=2' },
      { requirement: 'RTO ≤ 8 hours', standard: 'BIA', reference: 'B=2' },
      { requirement: 'Documented backup and restore procedures', standard: 'NEN 7510', reference: 'B=2' },
    );
  }

  if (I === 3) {
    controls.push(
      { requirement: 'Data validation mandatory on all data entry points', standard: 'NEN 7510', reference: 'I=3' },
      { requirement: 'NEN 7513 audit logging for all patient data access', standard: 'NEN 7513', reference: 'I=3' },
      { requirement: 'Data integrity checks (checksums, hash verification)', standard: 'Architecture', reference: 'I=3' },
      { requirement: 'Four-eyes principle for critical data modifications', standard: 'NEN 7510', reference: 'I=3' },
    );
  } else if (I === 2) {
    controls.push(
      { requirement: 'Application-level data validation', standard: 'Architecture', reference: 'I=2' },
      { requirement: 'Audit logging for data modifications', standard: 'NEN 7510', reference: 'I=2' },
    );
  }

  if (V === 3) {
    controls.push(
      { requirement: 'NEN 7510 full scope compliance', standard: 'NEN 7510', reference: 'V=3' },
      { requirement: 'DPIA mandatory (AVG Article 35)', standard: 'AVG/GDPR', reference: 'V=3' },
      { requirement: 'Encryption at rest and in transit for all data', standard: 'NEN 7512', reference: 'V=3' },
      { requirement: 'NEN 7513 audit logging for all patient data access', standard: 'NEN 7513', reference: 'V=3' },
      { requirement: 'Access control based on least privilege (RBAC/ABAC)', standard: 'NEN 7510', reference: 'V=3' },
    );
  } else if (V === 2) {
    controls.push(
      { requirement: 'Encryption in transit (TLS 1.2+)', standard: 'NEN 7512', reference: 'V=2' },
      { requirement: 'Access control (RBAC)', standard: 'NEN 7510', reference: 'V=2' },
      { requirement: 'DPIA assessment required', standard: 'AVG/GDPR', reference: 'V=2' },
    );
  }

  return controls;
}

// ---------------------------------------------------------------------------
// Bilingual — NL/EN language switching
// ---------------------------------------------------------------------------

const NL_EN = {
  'Akkoord': { nl: 'Akkoord', en: 'Approve' },
  'Voorwaardelijk': { nl: 'Voorwaardelijk', en: 'Conditional' },
  'Bezorgd': { nl: 'Bezorgd', en: 'Concern' },
  'Blokkade': { nl: 'Blokkade', en: 'Block' },
  'N.v.t.': { nl: 'N.v.t.', en: 'N/A' },
  'Vetorecht': { nl: 'Vetorecht', en: 'Veto' },
  'Escalatie': { nl: 'Escalatie', en: 'Escalation' },
  'Onafhankelijk': { nl: 'Onafhankelijk', en: 'Independent' },
  'Concept': { nl: 'Concept', en: 'Draft' },
  'Goedkeuren': { nl: 'Goedkeuren', en: 'Approve' },
  'Goedkeuren met voorwaarden': { nl: 'Goedkeuren met voorwaarden', en: 'Approve with conditions' },
  'Afwijzen': { nl: 'Afwijzen', en: 'Reject' },
  'Uitstellen': { nl: 'Uitstellen', en: 'Defer' },
  'Beschikbaarheid': { nl: 'Beschikbaarheid', en: 'Availability' },
  'Integriteit': { nl: 'Integriteit', en: 'Integrity' },
  'Vertrouwelijkheid': { nl: 'Vertrouwelijkheid', en: 'Confidentiality' },
  'fast-track': { nl: 'fast-track', en: 'fast-track' },
  'standard-review': { nl: 'standaardbeoordeling', en: 'standard review' },
  'deep-review': { nl: 'diepgaande beoordeling', en: 'deep review' },
};

/**
 * Translate a term or switch document language.
 * Usage: t('Akkoord', 'nl') → 'Akkoord', t('Akkoord', 'en') → 'Approve'
 */
export function t(term, lang = 'nl') {
  const entry = NL_EN[term];
  return entry ? entry[lang] : term;
}

/**
 * Switch an entire document's language markers.
 * Replaces [NL/EN] bilingual pairs based on selected language.
 */
export function switchLanguage(text, lang = 'nl') {
  // Replace bilingual markers: <!--NL:dutch text--><!--EN:english text-->
  return text.replace(/<!--NL:(.+?)--><!--EN:(.+?)-->/g, (_, nl, en) => {
    return lang === 'nl' ? nl : en;
  });
}