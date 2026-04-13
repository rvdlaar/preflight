/**
 * synthesis/engine.mjs — Document synthesis engine for Preflight.
 *
 * Takes persona assessment outputs and produces draft architecture documents.
 * Deterministic where possible, constrained LLM where necessary.
 *
 * * Principles:
 *   1. Templates are files, not code — template changes require zero code changes
 *   2. Structured fields (ratings, BIV, conditions, ZiRA) are filled deterministically
 *   3. LLM is used ONLY for synthesis sections (exec summary, recommendation)
 *   4. Every generated document is DRAFT — human sign-off is non-negotiable
 *   5. Diagrams are generated from structured element data, not prose parsing
 *   6. Every claim must cite its source — persona name for deterministic fields,
 *      knowledge chunk ID for LLM synthesis. Uncited claims are flagged for review.
 */

import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = resolve(__dirname, '..', 'templates');

// ---------------------------------------------------------------------------
// Template loading — templates are Markdown files with {{placeholder}} syntax
// ---------------------------------------------------------------------------

export function loadTemplate(name) {
  const path = resolve(TEMPLATES_DIR, `${name}.md`);
  return readFileSync(path, 'utf-8');
}

// ---------------------------------------------------------------------------
// Placeholder resolution — deterministic field mapping
// ---------------------------------------------------------------------------

/**
 * Resolve all {{placeholder}} values in a template string.
 * Placeholders are looked up in the context object.
 * Unresolved placeholders are left as-is (human fills them later).
 */
export function resolvePlaceholders(template, context) {
  return template.replace(/\{\{(\w[\w.]*)\}\}/g, (_, path) => {
    const value = resolvePath(context, path);
    return value !== undefined ? value : `{{${path}}}`;
  });
}

function resolvePath(obj, path) {
  return path.split('.').reduce((node, key) => node?.[key], obj);
}

// ---------------------------------------------------------------------------
// Assessment context builder — transforms persona outputs into template context
// ---------------------------------------------------------------------------

const ZIRA_PRINCIPLES = [
  'Waardevol', 'Veilig en vertrouwd', 'Duurzaam', 'Continu',
  'Mens centraal', 'Samen', 'Gestandaardiseerd', 'Flexibel',
  'Eenvoudig', 'Onder eigenaarschap', 'Datagedreven', 'Innovatief',
];

const RATING_NL = {
  approve: 'Akkoord',
  conditional: 'Voorwaardelijk',
  concern: 'Bezorgd',
  block: 'Blokkade',
  na: 'N.v.t.',
};

const AUTHORITY_NL = {
  VETO: 'Vetorecht',
  ESCALATION: 'Escalatie',
  INDEPENDENT: 'Onafhankelijk',
  CHALLENGE: 'Aanvechtging',
};

/**
 * Build a flat context object from persona assessment outputs,
 * suitable for template placeholder resolution.
 *
 * @param {object} input
 * @param {string} input.proposalName — name of the proposal
 * @param {string} input.requestType — classified request type
 * @param {object} input.ratings — { perspectiveId: rating } from parseAssessmentRatings
 * @param {Array}  input.personaFindings — [{ name, role, rating, findings, conditions, authority }]
 * @param {object} input.triage — from determineTriageLevel
 * @param {object} input.zira — ZiRA positioning data
 * @param {object} input.biv — { B, I, V, rpo, rto, determinedBy }
 * @param {string} input.assessmentMode — 'fast' | 'deep'
 * @param {object} input.landscape — enrichment data
 * @returns {object} flat context for template resolution
 */
export function buildContext(input) {
  const {
    proposalName = '[voorstel naam]',
    requestType = 'new-application',
    ratings = {},
    personaFindings = [],
    triage = {},
    zira = {},
    biv = {},
    assessmentMode = 'fast',
    landscape = {},
  } = input;

  const today = new Date().toISOString().split('T')[0];
  const blocks = personaFindings.filter(p => p.rating === 'block');
  const conditions = personaFindings.filter(p => p.rating === 'conditional');
  const vetoUsed = blocks.find(p => p.authority === 'VETO');
  const escalationUsed = blocks.find(p => p.authority === 'ESCALATION');

  return {
    // Metadata
    proposal_name: proposalName,
    date: today,
    version: '0.1',
    status: 'DRAFT',
    assessment_mode: assessmentMode === 'deep' ? 'Deep (panel)' : 'Fast (batched)',
    psa_id: `PSA-${today.replace(/-/g, '')}`,

    // BIV
    biv_b: biv.B ?? '_',
    biv_i: biv.I ?? '_',
    biv_v: biv.V ?? '_',
    biv_rpo: biv.rpo ?? '[RPO]',
    biv_rto: biv.rto ?? '[RTO]',

    // Triage
    treatment: triage.treatment ?? '[triage]',
    triage_reason: triage.reason ?? '',

    // Recommendation (driven by ratings, not LLM)
    recommendation: deriveRecommendation(ratings, blocks),
    board_time: deriveBoardTime(ratings, triage),

    // ZiRA
    zira_domain: zira.domain ?? '[Zorg | Onderzoek | Onderwijs | Sturing | Bedrijfsondersteuning]',
    zira_domain_secondary: zira.secondaryDomain ?? '',

    // Authority flags
    veto_exercised: vetoUsed ? `Ja — door ${vetoUsed.name}: ${vetoUsed.findings?.[0] ?? '[reden]'}` : 'Nee',
    escalation: escalationUsed ? `Ja — door ${escalationUsed.name}: ${escalationUsed.findings?.[0] ?? '[reden]'}` : 'Nee',
    fg_determination: blocks.find(p => p.authority === 'INDEPENDENT')
      ? 'Concept — bevestiging door FG vereist'
      : 'N.v.t.',

    // Counts
    block_count: blocks.length,
    condition_count: conditions.length,
  };
}

function deriveRecommendation(ratings, blocks) {
  if (blocks.some(b => b.authority === 'VETO' || b.authority === 'INDEPENDENT'))
    return 'Afwijzen';
  if (blocks.length > 0) return 'Uitstellen';
  if (Object.values(ratings).filter(r => r === 'concern').length >= 2)
    return 'Goedkeuren met voorwaarden';
  if (Object.values(ratings).some(r => r === 'conditional'))
    return 'Goedkeuren met voorwaarden';
  return 'Goedkeuren';
}

function deriveBoardTime(ratings, triage) {
  if (triage.treatment === 'deep-review') return 'volledige sessie';
  if (triage.treatment === 'standard-review') return '30 min';
  return '15 min';
}

// ---------------------------------------------------------------------------
// Citation system — every claim traces to a source
//
// Two source types:
//   1. PERSONA — deterministic, from persona findings: "Victor", "Nadia", etc.
//   2. KNOWLEDGE — from RAG retrieval: chunk ID with provenance
//
// Citation format in documents: [§source-type:id] e.g. [§P:Victor], [§K:nen7510-3.2]
// This makes it trivial to verify or strip citations post-generation.
// ---------------------------------------------------------------------------

const CITATION_PREFIX = '§';

/**
 * Create a persona citation. Used when a claim comes directly from
 * a persona's assessment output.
 *
 * @param {string} personaName — e.g. "Victor", "Nadia"
 * @param {string} [field] — optional specific field, e.g. "findings", "conditions"
 * @returns {string} citation tag like "[§P:Victor]" or "[§P:Victor.findings]"
 */
export function citePersona(personaName, field) {
  return field
    ? `[${CITATION_PREFIX}P:${personaName}.${field}]`
    : `[${CITATION_PREFIX}P:${personaName}]`;
}

/**
 * Create a knowledge base citation. Used when a claim is grounded in
 * a retrieved knowledge chunk (regulation, standard, policy document).
 *
 * @param {string} sourceId — e.g. "nen7510-3.2", "avg-art35", "zira-principe-8"
 * @param {string} [excerpt] — optional short excerpt for inline context
 * @returns {string} citation tag like "[§K:nen7510-3.2]"
 */
export function citeKnowledge(sourceId, excerpt) {
  return excerpt
    ? `[${CITATION_PREFIX}K:${sourceId}: "${excerpt}"]`
    : `[${CITATION_PREFIX}K:${sourceId}]`;
}

/**
 * Parse all citations from a document string.
 * Returns arrays of persona and knowledge citations with their positions.
 *
 * @param {string} text — document text with citation tags
 * @returns {{ persona: Array, knowledge: Array }}
 */
export function parseCitations(text) {
  const persona = [];
  const knowledge = [];

  const personaRegex = /\[§P:([A-Za-z-]+)(?:\.([a-z]+))?\]/g;
  const knowledgeRegex = /\[§K:([a-z0-9-]+)(?:: "([^"]+)")?\]/g;

  let match;
  while ((match = personaRegex.exec(text)) !== null) {
    persona.push({ name: match[1], field: match[2] ?? null, index: match.index });
  }
  while ((match = knowledgeRegex.exec(text)) !== null) {
    knowledge.push({ id: match[1], excerpt: match[2] ?? null, index: match.index });
  }

  return { persona, knowledge };
}

/**
 * Strip citations from text, leaving clean prose.
 * Useful for final document output after verification.
 */
export function stripCitations(text) {
  return text
    .replace(/\[§P:[A-Za-z-]+(?:\.[a-z]+)?\]/g, '')
    .replace(/\[§K:[a-z0-9-]+(?:: "[^"]+")?\]/g, '')
    .replace(/  +/g, ' ')
    .trim();
}

/**
 * Verify citations: check that every cited persona actually participated
 * in the assessment, and every knowledge source was actually retrieved.
 *
 * @param {string} text — document text with citations
 * @param {object} context — assessment context with personaFindings and sources
 * @returns {{ valid: boolean, unreferenced: string[], uncited: string[] }}
 *   unreferenced: sources cited in text but not in context
 *   uncited: sources in context but never cited in text
 */
export function verifyCitations(text, context) {
  const { personaFindings = [], sources = [] } = context;
  const citations = parseCitations(text);

  const participatingPersonas = new Set(personaFindings.map(p => p.name));
  const availableSources = new Set(sources.map(s => s.id));

  const citedPersonas = new Set(citations.persona.map(c => c.name));
  const citedSources = new Set(citations.knowledge.map(c => c.id));

  const unreferenced = [
    ...citations.persona
      .filter(c => !participatingPersonas.has(c.name))
      .map(c => `Persona "${c.name}" cited but did not participate in assessment`),
    ...citations.knowledge
      .filter(c => !availableSources.has(c.id))
      .map(c => `Source "${c.id}" cited but not in retrieved knowledge`),
  ];

  const uncited = [
    ...participatingPersonas
      .difference?.(citedPersonas) ?? [...participatingPersonas].filter(p => !citedPersonas.has(p)),
    ...availableSources
      .difference?.(citedSources) ?? [...availableSources].filter(s => !citedSources.has(s)),
  ];

  // Filter uncited to only show meaningful omissions
  // (don't flag every knowledge chunk that wasn't cited, only persona findings)
  const uncitedPersonas = [...participatingPersonas].filter(p => !citedPersonas.has(p));

  return {
    valid: unreferenced.length === 0,
    unreferenced,
    uncited: uncitedPersonas.length > 0
      ? [`Personas not cited in document: ${uncitedPersonas.join(', ')}`]
      : [],
  };
}

/**
 * Generate a citation appendix for a document.
 * Lists all sources used, grouped by type.
 */
export function generateCitationAppendix(personaFindings = [], sources = []) {
  const lines = ['## Bronvermelding / Sources', ''];

  if (personaFindings.length > 0) {
    lines.push('### Persoonlijke bronnen / Persona sources');
    lines.push('');
    lines.push('| Persona | Rol | Autoriteit |');
    lines.push('|---------|-----|------------|');
    for (const pf of personaFindings) {
      lines.push(`| ${pf.name} | ${pf.role} | ${AUTHORITY_NL[pf.authority] ?? '-'} |`);
    }
    lines.push('');
  }

  if (sources.length > 0) {
    lines.push('### Kennisbronnen / Knowledge sources');
    lines.push('');
    lines.push('| ID | Bron / Source | Type | Relevantie / Relevance |');
    lines.push('|----|---------------|------|------------------------|');
    for (const s of sources) {
      lines.push(`| ${s.id} | ${s.title ?? s.id} | ${s.type ?? 'document'} | ${s.relevance ?? '-'} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Build the LLM prompt constraint that forces citation.
 * This is prepended to any LLM synthesis prompt.
 * The LLM MUST cite claims using the [§P:name] and [§K:id] format.
 */
export function citationConstraintPrompt(personaFindings = [], sources = []) {
  const personaList = personaFindings.map(p => p.name).join(', ') || '(none)';
  const sourceList = sources.map(s => s.id).join(', ') || '(none)';

  return `CITATION RULES — YOU MUST FOLLOW THESE:

1. Every factual claim MUST cite its source using bracket notation.
2. Use [§P:PersonaName] for claims from persona assessments. Available: ${personaList}.
3. Use [§K:source-id] for claims from knowledge retrieval. Available: ${sourceList}.
4. If you cannot verify a claim from available sources, write "[VERIFY]" after it.
5. Do NOT fabricate source IDs. Only use sources listed above.
6. Do NOT make claims without citations. Uncited claims will be flagged for human review.

Example: "The proposed system handles patient data [§P:Aisha] and must comply with NEN 7513 logging requirements [§K:nen7510-12.4.1]."
Example: "Victor identified a risk of unencrypted data in transit [§P:Victor]."

These rules are non-negotiable. A document with uncited claims is incomplete.`;
}

// ---------------------------------------------------------------------------
// Document generation — template + context = draft document
// ---------------------------------------------------------------------------

/**
 * Generate a draft document from a template and assessment context.
 *
 * @param {string} templateName — template file name without .md (e.g., 'psa', 'adr')
 * @param {object} context — from buildContext()
 * @returns {string} — draft document with resolved placeholders
 */
export function generateDocument(templateName, context) {
  const template = loadTemplate(templateName);
  return resolvePlaceholders(template, context);
}

// ---------------------------------------------------------------------------
// Multi-document generation — produce all relevant documents for an assessment
// ---------------------------------------------------------------------------

/**
 * Determine which documents to generate based on request type and ratings.
 * Not every assessment needs all 15 products.
 *
 * @param {string} requestType
 * @param {object} ratings — { perspectiveId: rating }
 * @param {object} biv — { B, I, V }
 * @returns {string[]} — list of template names to generate
 */
export function determineRequiredDocuments(requestType, ratings = {}, biv = {}) {
  const docs = new Set(['psa', 'adr']);

  // Always produce PSA + ADR
  // Security assessment if Victor is concerned or blocks
  if (['block', 'concern'].includes(ratings.security)) docs.add('security-assessment');

  // BIA if any BIV dimension is 3
  if ([biv.B, biv.I, biv.V].some(v => v === 3)) docs.add('bia-biv');

  // DPIA if FG-DPO is involved or patient data
  if (['block', 'concern'].includes(ratings['fg-dpo']) || requestType === 'patient-data' || requestType === 'clinical-system') {
    docs.add('dpia');
  }

  // Clinical impact for clinical systems
  if (requestType === 'clinical-system') docs.add('clinical-impact');

  // Integration design if Lena is involved
  if (['block', 'concern'].includes(ratings.integration) || requestType === 'integration') {
    docs.add('integration-design');
  }

  // Network impact if Ruben is involved
  if (['block', 'concern'].includes(ratings.network)) docs.add('network-impact');

  // Process impact if Joris is involved
  if (['block', 'concern'].includes(ratings.process)) docs.add('process-impact');

  // EU AI Act if AI/ML
  if (requestType === 'ai-ml') docs.add('eu-ai-act');

  // Vendor assessment if new vendor
  if (requestType === 'vendor-selection') docs.add('vendor-assessment');

  // NFR spec for high-impact
  if (ratings.solution === 'concern' || ratings.solution === 'block') docs.add('nfr-specification');

  // Operational readiness for anything going to production
  docs.add('operational-readiness');

  // Tech radar update for new technology
  if (requestType === 'new-application' || requestType === 'infrastructure-change') {
    docs.add('tech-radar-update');
  }

  // Roadmap impact if portfolio is involved
  if (['block', 'concern'].includes(ratings.portfolio)) docs.add('roadmap-impact');

  return [...docs];
}

/**
 * Generate all required documents for an assessment.
 *
 * @param {object} input — same as buildContext input
 * @returns {object} — { templateName: draftContent }
 */
export function generateAllDocuments(input) {
  const context = buildContext(input);
  const requiredDocs = determineRequiredDocuments(input.requestType, input.ratings, input.biv);

  const documents = {};
  for (const docName of requiredDocs) {
    try {
      documents[docName] = generateDocument(docName, context);
    } catch {
      // Template doesn't exist yet — skip silently, it'll be created later
    }
  }

  return documents;
}

// ---------------------------------------------------------------------------
// Persona findings table generation — for PSA section 6
// ---------------------------------------------------------------------------

/**
 * Generate the domain assessments section (PSA section 6) from persona findings.
 * This is deterministic — no LLM involved.
 */
export function formatPersonaFindings(personaFindings) {
  const sections = [];
  const overviewRows = [];

  for (const pf of personaFindings) {
    sections.push(`### 6.${sections.length + 1} ${pf.name} — ${pf.role}`);
    sections.push('');
    sections.push(`**Beoordeling / Rating:** ${RATING_NL[pf.rating] ?? pf.rating}`);
    sections.push('');
    if (pf.findings?.length) {
      sections.push('**Bevindingen / Findings:**');
      for (const f of pf.findings) sections.push(`- ${f}`);
      sections.push('');
    }
    if (pf.conditions?.length) {
      sections.push('**Voorwaarden / Conditions:**');
      for (const c of pf.conditions) sections.push(`- ${c}`);
      sections.push('');
    }
    sections.push('---');
    sections.push('');

    overviewRows.push(
      `| ${pf.role} | ${pf.name} | ${RATING_NL[pf.rating] ?? pf.rating} | ${AUTHORITY_NL[pf.authority] ?? '-'} |`
    );
  }

  const overview = [
    '### Beoordelingsoverzicht / Assessment Overview',
    '',
    '| Persona | Naam | Rating | Bijzondere bevoegdheid |',
    '|---------|------|--------|------------------------|',
    ...overviewRows,
    '',
  ];

  return [...overview, ...sections].join('\n');
}

// ---------------------------------------------------------------------------
// Risk register generation — from persona findings
// ---------------------------------------------------------------------------

/**
 * Extract risk register entries from persona findings.
 * Each finding with a risk signal gets a row.
 */
export function generateRiskRegister(personaFindings) {
  const rows = [];
  let riskNum = 1;

  for (const pf of personaFindings) {
    if (pf.rating === 'approve' || pf.rating === 'na') continue;
    for (const finding of (pf.findings ?? [])) {
      rows.push(
        `| R${riskNum} | ${finding} | ${pf.rating === 'block' ? 'H' : 'M'} | ${pf.rating === 'block' ? 'H' : 'M'} | ${pf.rating === 'block' ? 'H' : 'M'} | ${pf.name} | [mitigerende maatregel] |`
      );
      riskNum++;
    }
  }

  return rows.length > 0
    ? `| # | Risico | Kans | Impact | Score | Bron (persona) | Mitigatie |\n|---|--------|------|--------|-------|----------------|-----------|\n${rows.join('\n')}`
    : '| # | Risico | Kans | Impact | Score | Bron (persona) | Mitigatie |\n|---|--------|------|--------|-------|----------------|-----------|\n| - | Geen risico\'s geïdentificeerd | - | - | - | - | - |';
}

// ---------------------------------------------------------------------------
// Conditions table generation — for PSA section 10
// ---------------------------------------------------------------------------

export function generateConditionsTable(personaFindings) {
  const rows = [];
  let condNum = 1;

  for (const pf of personaFindings) {
    if (!pf.conditions?.length) continue;
    for (const cond of pf.conditions) {
      rows.push(`| C${condNum} | ${cond} | ${pf.name} | [eigenaar] | [datum] | Open |`);
      condNum++;
    }
  }

  return rows.length > 0
    ? `| # | Voorwaarde | Bron (persona) | Eigenaar | Deadline | Status |\n|---|-----------|----------------|----------|----------|--------|\n${rows.join('\n')}`
    : '| # | Voorwaarde | Bron (persona) | Eigenaar | Deadline | Status |\n|---|-----------|----------------|----------|----------|--------|\n| - | Geen voorwaarden | - | - | - | - |';
}