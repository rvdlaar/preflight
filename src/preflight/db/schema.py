"""
Preflight database schema — PostgreSQL with graph traversal support.

Design decisions:
- PostgreSQL (not MongoDB): relational integrity, SQL for analytics,
  pgvector for RAG, CTEs for graph traversal
- UUIDs everywhere: no sequential IDs that leak information
- JSONB for flexible data: persona findings, regulatory details
- Append-only for assessments: v1 is never modified, v2 has parent pointer
- Hash-chained audit log: NEN 7513 compliant, tamper-evident
- Every entity tracks: who created it, when, from what source

The schema is organized into domains:
  1. Core — requests, assessments, lifecycle
  2. Personas — findings, ratings, versions
  3. Authority — vetoes, escalations, sign-offs
  4. Conditions — lifecycle tracking
  5. Decisions — board records, overrides
  6. Retrospectives — did the risk materialize?
  7. Calibration — persona accuracy vs board decisions
  8. Knowledge — sources, citations, verification
  9. Landscape — vendors, systems, debt
  10. Audit — NEN 7513 hash-chained log
"""

# ---------------------------------------------------------------------------
# Migrations are SQL files, not ORM models.
# This file defines the schema as SQL DDL for clarity and review.
# In production, use Alembic for migration management.
# ---------------------------------------------------------------------------

SCHEMA_CORE = """
-- ============================================================
-- DOMAIN 1: CORE — requests, assessments, lifecycle
-- ============================================================

CREATE TABLE request (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id    TEXT UNIQUE,                    -- human-readable: REQ-20250410-001
    description    TEXT NOT NULL,                  -- the business request text
    
    -- Classification (from Step 1)
    request_type   TEXT NOT NULL,                  -- new-application, clinical-system, etc.
    impact_level   TEXT NOT NULL,                  -- low, medium, high, critical
    triage_floor_applied TEXT[],                   -- which floors triggered
    
    -- Lifecycle
    state          TEXT NOT NULL DEFAULT 'SUBMITTED',
    submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_by   UUID NOT NULL REFERENCES "user"(id),  -- FK to user table
    
    -- Metadata
    attachments    JSONB DEFAULT '[]'::jsonb,     -- [{name, path, type, parsed}]
    adaptive_fields JSONB DEFAULT '{}'::jsonb,     -- intake form responses
    
    -- Landscape context (from Step 0)
    landscape_context JSONB DEFAULT '{}'::jsonb,   -- ArchiMate query results
    
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lifecycle state machine (enforced at application level)
-- SUBMITTED → PRELIMINARY → CLARIFICATION → ASSESSED → BOARD_READY 
-- → IN_REVIEW → DECIDED → CONDITIONS_OPEN → CLOSED

CREATE TABLE assessment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id    TEXT UNIQUE,                    -- PSA-20250410
    request_id     UUID NOT NULL REFERENCES request(id),
    
    -- Versioning (append-only)
    version        INTEGER NOT NULL DEFAULT 1,
    parent_id      UUID REFERENCES assessment(id),-- null for v1, points to previous for deltas
    
    -- Assessment configuration
    assessment_mode TEXT NOT NULL DEFAULT 'fast',  -- fast | deep
    selected_perspectives TEXT[] NOT NULL,          -- which perspectives were active
    
    -- Triage result
    triage_treatment TEXT NOT NULL,                 -- fast-track | standard-review | deep-review
    triage_reason   TEXT,
    
    -- BIV
    biv_b          SMALLINT NOT NULL DEFAULT 2,    -- 1-3
    biv_i          SMALLINT NOT NULL DEFAULT 2,
    biv_v          SMALLINT NOT NULL DEFAULT 2,
    biv_rpo        TEXT,
    biv_rto        TEXT,
    
    -- ZiRA
    zira_domain    TEXT,
    zira_positioning JSONB DEFAULT '{}'::jsonb,   -- bedrijfsfuncties, diensten, etc.
    
    -- Recommendation (deterministic from ratings)
    recommendation TEXT NOT NULL,                   -- approve | conditional | reject | defer
    board_time_est TEXT,                            -- 15 min | 30 min | full session
    
    -- Persona version snapshot (for MDR traceability)
    persona_version TEXT NOT NULL,                  -- which persona version produced this
    persona_hash   TEXT NOT NULL,                   -- checksum of persona definitions
    
    -- Output
    documents      JSONB DEFAULT '{}'::jsonb,      -- {template_name: content}
    diagrams       JSONB DEFAULT '{}'::jsonb,       -- {diagram_name: {xml, mermaid}}
    principetoets  JSONB DEFAULT '{}'::jsonb,       -- 12 principles evaluation
    risk_register  JSONB DEFAULT '[]'::jsonb,
    citation_appendix TEXT,
    
    -- Clarification questions (generated before assessment)
    clarification_questions JSONB DEFAULT '[]'::jsonb,
    
    -- Delta tracking
    delta_changes  JSONB DEFAULT '[]'::jsonb,       -- what changed from parent assessment
    reassessed_perspectives TEXT[],                  -- which personas were re-assessed
    
    -- Metadata
    status         TEXT NOT NULL DEFAULT 'DRAFT',   -- DRAFT | ARCHITECT_REVIEWED | BOARD_READY
    reviewed_by    UUID REFERENCES "user"(id),
    reviewed_at    TIMESTAMPTZ,
    
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE(request_id, version)
);
CREATE INDEX idx_assessment_request ON assessment(request_id);
CREATE INDEX idx_assessment_parent ON assessment(parent_id);

-- Clarification round (before assessment)
CREATE TABLE clarification (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID NOT NULL REFERENCES request(id),
    persona_name    TEXT NOT NULL,
    persona_role    TEXT NOT NULL,
    question        TEXT NOT NULL,
    reason          TEXT,
    required        BOOLEAN NOT NULL DEFAULT true,
    
    answered        BOOLEAN NOT NULL DEFAULT false,
    answer          TEXT,
    answered_by     UUID REFERENCES "user"(id),
    answered_at     TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

SCHEMA_PERSONAS = """
-- ============================================================
-- DOMAIN 2: PERSONAS — findings, ratings, versions
-- ============================================================

CREATE TABLE persona_version (
    version        TEXT PRIMARY KEY,              -- "1.0.0"
    date           DATE NOT NULL,
    persona_count  INTEGER NOT NULL,
    definition_hash TEXT NOT NULL,                 -- checksum of persona definitions
    changelog      TEXT,
    
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE persona_finding (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    perspective_id  TEXT NOT NULL,                 -- cio, chief, security, etc.
    persona_name    TEXT NOT NULL,                  -- Victor, Nadia, etc.
    persona_role    TEXT NOT NULL,                  -- Security Architecture, etc.
    
    -- Rating
    rating          TEXT NOT NULL,                 -- approve | conditional | concern | block | na
    
    -- Authority
    authority_type  TEXT,                           -- VETO | ESCALATION | INDEPENDENT | CHALLENGE
    authority_triggered BOOLEAN DEFAULT false,
    
    -- Findings
    findings        JSONB DEFAULT '[]'::jsonb,     -- [{finding, source, citation}]
    conditions      JSONB DEFAULT '[]'::jsonb,     -- [{condition, measurable, source}]
    hidden_concern  TEXT,                           -- from deep mode
    strongest_objection TEXT,                       -- from deep mode
    
    -- Context used (for traceability)
    knowledge_bundle_ids TEXT[],                    -- which knowledge chunks were retrieved
    landscape_context_applied JSONB DEFAULT '{}'::jsonb,
    
    -- Persona version at time of assessment
    persona_version TEXT NOT NULL REFERENCES persona_version(version),
    
    -- Board override tracking (for calibration)
    board_override  BOOLEAN DEFAULT false,
    override_reason TEXT,
    overridden_by   UUID REFERENCES "user"(id),
    overridden_at   TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_finding_assessment ON persona_finding(assessment_id);
CREATE INDEX idx_finding_persona ON persona_finding(persona_name);
CREATE INDEX idx_finding_rating ON persona_finding(rating);
CREATE INDEX idx_finding_override ON persona_finding(board_override) WHERE board_override = true;
"""

SCHEMA_AUTHORITY = """
-- ============================================================
-- DOMAIN 3: AUTHORITY — vetoes, escalations, sign-offs
-- ============================================================

CREATE TABLE authority_action (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    finding_id      UUID NOT NULL REFERENCES persona_finding(id),
    
    action_type     TEXT NOT NULL,                  -- VETO | ESCALATION | INDEPENDENT_DETERMINATION | PATIENT_SAFETY
    persona_name    TEXT NOT NULL,
    label           TEXT NOT NULL,                  -- "Security Veto", "FG Determination"
    
    -- Sign-off workflow (ALL authority outputs are DRAFTS)
    requires_sign_off TEXT NOT NULL,                -- security-architect | compliance-officer | fg-dpo | cmio
    sign_off_status TEXT NOT NULL DEFAULT 'PENDING',-- PENDING | APPROVED | REJECTED
    signed_off_by   UUID REFERENCES "user"(id),
    signed_off_at   TIMESTAMPTZ,
    sign_off_notes  TEXT,
    
    -- Pipeline control
    pipeline_halted BOOLEAN DEFAULT false,
    halt_reason     TEXT,
    
    -- Draft disclaimer
    draft_disclaimer TEXT NOT NULL,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_authority_assessment ON authority_action(assessment_id);
CREATE INDEX idx_authority_signoff ON authority_action(sign_off_status) WHERE sign_off_status = 'PENDING';
"""

SCHEMA_CONDITIONS = """
-- ============================================================
-- DOMAIN 4: CONDITIONS — lifecycle tracking
-- ============================================================

CREATE TABLE condition (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id    TEXT UNIQUE,                     -- PSA-20250410-C1
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    
    condition_text  TEXT NOT NULL,
    source_persona  TEXT NOT NULL,
    source_finding_id UUID REFERENCES persona_finding(id),
    
    -- Lifecycle
    status          TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN | IN_PROGRESS | MET | WAIVED | OVERDUE
    owner           UUID REFERENCES "user"(id),
    due_date        DATE,
    evidence        TEXT,
    
    -- Tracking
    reminders_sent  INTEGER DEFAULT 0,
    last_reminder_at TIMESTAMPTZ,
    escalation_count INTEGER DEFAULT 0,
    escalation_to   TEXT,
    
    -- Resolution
    resolved_by    UUID REFERENCES "user"(id),
    resolved_at    TIMESTAMPTZ,
    resolution_notes TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_condition_assessment ON condition(assessment_id);
CREATE INDEX idx_condition_owner ON condition(owner) WHERE status IN ('OPEN', 'IN_PROGRESS');
CREATE INDEX idx_condition_overdue ON condition(due_date) WHERE status = 'OPEN' AND due_date < CURRENT_DATE;
"""

SCHEMA_DECISIONS = """
-- ============================================================
-- DOMAIN 5: DECISIONS — board records, overrides
-- ============================================================

CREATE TABLE board_decision (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    
    decision        TEXT NOT NULL,                  -- approve | conditional | reject | defer
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by      UUID NOT NULL REFERENCES "user"(id),  -- board chair
    
    -- Per-item breakdown
    items           JSONB DEFAULT '[]'::jsonb,     -- [{finding_id, decision, reason}]
    
    -- Board time
    board_time_actual INTERVAL,                     -- actual vs estimated
    
    -- Board notes
    notes           TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_decision_assessment ON board_decision(assessment_id);

CREATE TABLE board_override (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id     UUID NOT NULL REFERENCES board_decision(id),
    finding_id      UUID NOT NULL REFERENCES persona_finding(id),
    
    original_rating TEXT NOT NULL,                  -- what the persona said
    override_decision TEXT NOT NULL,                -- what the board decided
    override_reason TEXT NOT NULL,                  -- why
    
    overriden_by    UUID NOT NULL REFERENCES "user"(id),
    overriden_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Calibration signal: was this override right?
    retrospective_validated BOOLEAN,                -- did the risk materialize?
    retrospective_notes TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_override_finding ON board_override(finding_id);
CREATE INDEX idx_override_retrospective ON board_override(retrospective_validated) WHERE retrospective_validated IS NOT NULL;
"""

SCHEMA_RETROSPECTIVE = """
-- ============================================================
-- DOMAIN 6: RETROSPECTIVES — did the risk materialize?
-- ============================================================

-- This is the closed loop that makes Preflight a learning system.
-- Without this table, the calibration features are impossible.

CREATE TABLE retrospective (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    
    -- When to review (typically 6-12 months after go-live)
    scheduled_date  DATE NOT NULL,
    completed_date  DATE,
    completed_by    UUID REFERENCES "user"(id),
    
    -- Per-finding outcomes
    finding_outcomes JSONB DEFAULT '[]'::jsonb,    
    -- [{finding_id, persona_name, predicted_risk, materialized: bool, 
    --   severity: low|medium|high, notes}]
    
    -- Per-condition outcomes
    condition_outcomes JSONB DEFAULT '[]'::jsonb,  
    -- [{condition_id, met: bool, met_when: date, evidence}]
    
    -- Overall assessment accuracy
    accuracy_score  REAL,                            -- 0-1: how many predictions were right
    
    -- Unpredicted events
    unpredicted_events JSONB DEFAULT '[]'::jsonb,   
    -- [{event, severity, why_no_persona_flagged_it}]
    
    -- Calibration recommendations (auto-generated)
    calibration_recommendations JSONB DEFAULT '[]'::jsonb,
    
    status          TEXT NOT NULL DEFAULT 'SCHEDULED',-- SCHEDULED | COMPLETED | SKIPPED
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_retrospective_assessment ON retrospective(assessment_id);
CREATE INDEX idx_retrospective_scheduled ON retrospective(scheduled_date) WHERE status = 'SCHEDULED';
"""

SCHEMA_CALIBRATION = """
-- ============================================================
-- DOMAIN 7: CALIBRATION — persona accuracy vs board decisions
-- ============================================================

-- This is the meta level. After N assessments, we can measure:
-- - Which personas are aligned with the board?
-- - Which personas are systematically overridden?
-- - Are we getting more conservative or more lenient?
-- - Is Victor's veto threshold right for clinical systems?

CREATE TABLE persona_calibration (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_name    TEXT NOT NULL,
    perspective_id  TEXT NOT NULL,
    
    -- Time window
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    
    -- Statistics
    total_assessments INTEGER NOT NULL DEFAULT 0,
    approve_count     INTEGER NOT NULL DEFAULT 0,
    conditional_count INTEGER NOT NULL DEFAULT 0,
    concern_count     INTEGER NOT NULL DEFAULT 0,
    block_count       INTEGER NOT NULL DEFAULT 0,
    
    -- Override statistics (THE calibration signal)
    override_count    INTEGER NOT NULL DEFAULT 0,
    override_rate     REAL,                           -- overrides / non-approve = rate
    override_decisions TEXT[],                        -- what board decided instead
    
    -- Retrospective accuracy
    predictions_correct INTEGER NOT NULL DEFAULT 0,  -- risks that materialized
    predictions_wrong   INTEGER NOT NULL DEFAULT 0,  -- risks that didn't
    retrospective_accuracy REAL,                      -- correct / (correct + wrong)
    
    -- Alignment score (combination of override rate + retrospective accuracy)
    alignment_score  REAL,                             -- 0-1: 1 = perfectly aligned with board
    
    -- Calibration recommendations (auto-generated from data)
    recommendation  TEXT,                              -- e.g., "Lower veto threshold for internal-only systems"
    recommended_change TEXT,                           -- e.g., "Add exception: VETO does not apply to internal-only with no patient data"
    
    -- Which data this calibration was based on
    assessment_ids UUID[],
    retrospective_ids UUID[],
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE(persona_name, perspective_id, period_start, period_end)
);
"""

SCHEMA_KNOWLEDGE = """
-- ============================================================
-- DOMAIN 8: KNOWLEDGE — sources, citations, verification
-- ============================================================

CREATE TABLE knowledge_source (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT UNIQUE NOT NULL,            -- nen7510-12.4.1, avg-art35, etc.
    title           TEXT NOT NULL,
    source_type     TEXT NOT NULL,                    -- regulation | policy | standard | vendor_doc | principle
    language        TEXT NOT NULL DEFAULT 'nl',
    
    -- Content
    content         TEXT NOT NULL,
    chunk_text      TEXT NOT NULL,                    -- chunked version for RAG
    embedding       vector(1024),                     -- pgvector — model-dependent
    
    -- Metadata
    source_file     TEXT,
    page_number     INTEGER,
    section         TEXT,
    effective_date  DATE,
    
    -- Persona relevance (from auto-tagging)
    persona_relevance TEXT[],                         -- which personas should see this
    
    -- Classification
    classification  TEXT DEFAULT 'internal',          -- public | internal | confidential | patient-data
    
    -- Verification
    verified        BOOLEAN DEFAULT false,
    verified_by     UUID REFERENCES "user"(id),
    verified_at     TIMESTAMPTZ,
    
    -- Citations (how many times this source has been cited in assessments)
    citation_count  INTEGER DEFAULT 0,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_knowledge_embedding ON knowledge_source USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_persona ON knowledge_source USING gin(persona_relevance);
CREATE INDEX idx_knowledge_type ON knowledge_source(source_type);

CREATE TABLE knowledge_chunk (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    chunk_text      TEXT NOT NULL,
    context_prefix  TEXT DEFAULT '',
    enriched_keyword TEXT DEFAULT '',
    enriched_semantic TEXT DEFAULT '',
    language        TEXT DEFAULT 'nl',
    section         TEXT,
    page_number     INTEGER,
    persona_relevance TEXT[],
    content_type    TEXT DEFAULT 'generic',
    classification  TEXT DEFAULT 'internal',
    metadata        JSONB DEFAULT '{}',

    -- Vector columns (requires pgvector >= 0.7.0 for sparsevec)
    dense_vector    vector(1024),
    title_vector    vector(1024),
    -- sparse_vector   sparsevec,  -- Uncomment if pgvector >= 0.7.0
    content_ts      tsvector,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chunk_dense ON knowledge_chunk USING hnsw (dense_vector vector_cosine_ops);
CREATE INDEX idx_chunk_title ON knowledge_chunk USING hnsw (title_vector vector_cosine_ops);
CREATE INDEX idx_chunk_source ON knowledge_chunk(source_id);
CREATE INDEX idx_chunk_type ON knowledge_chunk(content_type);
CREATE INDEX idx_chunk_persona ON knowledge_chunk USING gin(persona_relevance);
CREATE INDEX idx_chunk_fts ON knowledge_chunk USING gin(content_ts);

-- Add sparsevec column if pgvector >= 0.7.0:
-- ALTER TABLE knowledge_chunk ADD COLUMN sparse_vector sparsevec;

CREATE TABLE citation (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id   UUID NOT NULL REFERENCES assessment(id),
    finding_id      UUID REFERENCES persona_finding(id),
    
    source_type     TEXT NOT NULL,                    -- PERSONA | KNOWLEDGE
    source_id       TEXT NOT NULL,                    -- persona name or knowledge_source.source_id
    excerpt         TEXT,
    
    -- Verification (post-generation citation check)
    verified        BOOLEAN,
    verification_failure TEXT,                        -- if unverifiable, why
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_citation_assessment ON citation(assessment_id);
CREATE INDEX idx_citation_source ON citation(source_type, source_id);
CREATE INDEX idx_citation_unverified ON citation(verified) WHERE verified = false OR verified IS NULL;
"""

SCHEMA_LANDSCAPE = """
-- ============================================================
-- DOMAIN 9: LANDSCAPE — vendors, systems, debt, graph edges
-- ============================================================

CREATE TABLE vendor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT UNIQUE NOT NULL,
    
    -- Intelligence profile (cumulative)
    assessments_count INTEGER DEFAULT 0,
    approval_rate    REAL,                             -- approved / total
    open_conditions  INTEGER DEFAULT 0,
    
    -- Compliance status
    nen7510_status   TEXT,                             -- certified | self-declared | unknown
    nen7512_status   TEXT,
    nen7513_status   TEXT,
    aivg_status      TEXT,
    dpa_in_place     BOOLEAN DEFAULT false,
    dpia_required    BOOLEAN,
    
    -- SBOM
    sbom_available   BOOLEAN DEFAULT false,
    sbom_format      TEXT,                             -- CycloneDX | SPDX | proprietary
    
    -- Portfolio presence
    systems_count    INTEGER DEFAULT 0,                -- how many hospital systems use this vendor
    
    -- Cumulative notes
    notes           TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE system (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archimate_id    TEXT UNIQUE,                       -- from Archi model element ID
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,                      -- ApplicationComponent | DataObject | etc.
    layer           TEXT NOT NULL,                      -- Business | Application | Technology
    
    -- Lifecycle
    lifecycle_status TEXT NOT NULL DEFAULT 'production',-- production | phase-out | planned | retired
    vendor_id       UUID REFERENCES vendor(id),
    
    -- BIV (from most recent assessment or manual)
    biv_b           SMALLINT,
    biv_i           SMALLINT,
    biv_v           SMALLINT,
    
    -- DR tier (driven by B)
    dr_tier         SMALLINT,                           -- 1 | 2 | 3
    
    -- Properties from ArchiMate
    properties      JSONB DEFAULT '{}'::jsonb,
    
    -- Debt tracking
    debt_items      JSONB DEFAULT '[]'::jsonb,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_system_archimate ON system(archimate_id);
CREATE INDEX idx_system_lifecycle ON system(lifecycle_status);

-- Graph edges — ArchiMate relationships as queryable edges
CREATE TABLE system_relationship (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES system(id),
    target_id       UUID NOT NULL REFERENCES system(id),
    relationship_type TEXT NOT NULL,                     -- Serving | Flow | Access | Triggering | etc.
    
    -- From which model
    source_model    TEXT NOT NULL DEFAULT 'hospital',    -- hospital | zira
    
    -- Strength for cascade analysis
    cascade_weight REAL DEFAULT 1.0,                     -- higher = more critical dependency
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE(source_id, target_id, relationship_type, source_model)
);
CREATE INDEX idx_rel_source ON system_relationship(source_id);
CREATE INDEX idx_rel_target ON system_relationship(target_id);

-- Architecture debt register
CREATE TABLE architecture_debt (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_id       UUID REFERENCES system(id),
    archimate_element_id TEXT,                          -- link to ArchiMate element
    
    debt_type       TEXT NOT NULL,                      -- technical | integration | security | compliance | portfolio
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'medium',     -- low | medium | high | critical
    
    -- Resolution tracking
    status          TEXT NOT NULL DEFAULT 'open',       -- open | planned | resolving | resolved
    resolves_via    UUID,                               -- assessment_id that would resolve this
    
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_debt_system ON architecture_debt(system_id);
CREATE INDEX idx_debt_severity ON architecture_debt(severity) WHERE status = 'open';
"""

SCHEMA_AUDIT = """
-- ============================================================
-- DOMAIN 10: AUDIT — NEN 7513 hash-chained log
-- ============================================================

-- Append-only. No UPDATE. No DELETE.
-- Enforced via PostgreSQL RLS + revoked permissions.

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- What happened
    event_type      TEXT NOT NULL,                     -- auth | authz | assessment | persona | veto | decision | calibration
    action          TEXT NOT NULL,                     -- created | accessed | denied | overridden | signed_off | ...
    
    -- Who did it
    actor_id        UUID NOT NULL REFERENCES "user"(id),
    actor_role      TEXT NOT NULL,                     -- RBAC role at time of action
    
    -- What was affected
    resource_type   TEXT,                              -- assessment | condition | finding | vendor | system
    resource_id     UUID,
    
    -- Context
    assessment_id   UUID,
    details         JSONB,
    
    -- Classification (for ABAC — who can see this log entry)
    classification  TEXT DEFAULT 'internal',          -- public | internal | confidential | patient-data
    
    -- Network
    source_ip       INET,
    user_agent      TEXT,
    
    -- Hash chain (NEN 7513 tamper evidence)
    previous_hash   TEXT NOT NULL,                     -- SHA-256 of previous entry
    entry_hash      TEXT NOT NULL                      -- SHA-256 of this entry
    
    -- Enforcement: no updates, no deletes
    -- Applied via: REVOKE UPDATE, DELETE ON audit_log FROM all roles;
);

-- Index for SIEM queries
CREATE INDEX idx_audit_type ON audit_log(event_type, timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_assessment ON audit_log(assessment_id) WHERE assessment_id IS NOT NULL;
"""

SCHEMA_USER = """
-- ============================================================
-- USER — minimal, backed by Entra ID in production
-- ============================================================

CREATE TABLE "user" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entra_id        TEXT UNIQUE,                       -- Entra ID user principal name
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    
    -- RBAC role
    role            TEXT NOT NULL DEFAULT 'requestor', -- requestor | architect | lead-architect | board-member | board-chair | chief-architect | cio | compliance-officer | fg-dpo | admin
    
    -- ABAC attributes
    department      TEXT,
    clearance_level TEXT DEFAULT 'internal',           -- public | internal | confidential | patient-data | export-clearance
    clinical_access BOOLEAN DEFAULT false,             -- can see patient-data assessments
    
    -- Preferences
    language        TEXT DEFAULT 'nl',                  -- nl | en
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Combined schema for initial migration
FULL_SCHEMA = (
    """
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

"""
    + SCHEMA_USER
    + SCHEMA_CORE
    + SCHEMA_PERSONAS
    + SCHEMA_AUTHORITY
    + SCHEMA_CONDITIONS
    + SCHEMA_DECISIONS
    + SCHEMA_RETROSPECTIVE
    + SCHEMA_CALIBRATION
    + SCHEMA_KNOWLEDGE
    + SCHEMA_LANDSCAPE
    + SCHEMA_AUDIT
)
