# Preflight — Technical Architecture

This document covers the implementation details behind Preflight's six-step pipeline. For what Preflight does and who it's for, see [PREFLIGHT.md](PREFLIGHT.md).

---

## Framework: NemoClaw

Preflight is built on **NemoClaw** — NVIDIA's enterprise AI stack (NeMo, NIM, Guardrails) combined with OpenClaw's patterns (MiroFish personas, simulatePanel protocol). The framework, not a specific model.

## LLM Strategy: Route by Reasoning Demand

Different steps have different reasoning demands. The LLM layer is a router that dispatches to the right tier:

| Tier | Used by | Requirement | Examples |
|------|---------|-------------|---------|
| **Light** | Steps 0, 1, 2, 5 | Fast, cheap, good instruction following | Small self-hosted model via NIM, Ollama for local dev |
| **Strong** | Step 3 | Nuanced reasoning, stays in character, structured output | Mid-size self-hosted model via NIM |
| **Frontier** | Step 4 | Best reasoning available | Frontier API call (when stakes justify cost), or best available self-hosted |

Cost goes where it matters: 80% of calls hit the light tier. The frontier tier only fires for high/critical impact proposals in Step 4.

**Phase 1 approach:** Start with a single model for all tiers. Instrument every step with quality metrics. Split the routing when you have data on where quality matters vs. where it's wasted.

```python
class LLMRouter:
    light: LLMClient     # Steps 0, 1, 2, 5
    strong: LLMClient    # Step 3
    frontier: LLMClient  # Step 4

class LLMClient(Protocol):
    async def call(self, system: str, user: str, opts: CallOpts) -> LLMResponse: ...
```

Behind each client: NIM endpoint, Ollama, or external API. The pipeline doesn't care. The personas don't care. `simulatePanel()` calls `router.strong.call()` and gets text back.

---

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | | |
| LLM | LLMRouter (pluggable — NIM, Ollama, API) | Tiered reasoning engine |
| Personas | MiroFish (ea-council-personas.mjs) | Drive every pipeline step |
| Orchestration | Python / FastAPI | Request flow, API layer |
| Knowledge store | Milvus (Phase 2+) / pgvector (Phase 1) | RAG over policies, principles, standards, tech radar |
| Embedding | Tiered: Voyage-3-Large, BGE-M3, Gemini 2.0 | Data-type-specific chunking + embedding |
| Guardrails | NeMo Guardrails | Input/output filtering, prompt injection defense |
| Document parsing | Tiered parsing pipeline | PDF, DOCX, PPTX, XLSX, scanned docs extraction |
| AuthN | Microsoft Entra ID (OIDC) | SSO via hospital identity provider |
| AuthZ | OAuth 2.1 + RBAC/ABAC policy engine | Token-based authorization with role and attribute policies |
| Audit trail | Append-only log (PostgreSQL) + SIEM integration | Immutable record of every assessment, access, and event |
| **Frontend** | | |
| Web UI | Next.js + shadcn/ui + Tailwind | Architect-facing interface — bilingual NL/EN |
| **Integrations** | | |
| ArchiMate (Archi) | .archimate XML parser | Application landscape, capabilities, interfaces, relationships |
| TOPdesk | REST API | CMDB, assets, CIs, change records, open risks, GRC |
| SharePoint | Microsoft Graph API | Architecture policies, standards, board decisions |
| OneDrive | Microsoft Graph API | Vendor docs, data sheets, proposal attachments |
| LeanIX | API | Application portfolio, lifecycle status, technology risk |

---

## Pipeline Implementation

### Step 0 — Ingest (Persona-Driven Discovery)

The front door. The architect feeds Preflight:

**Required:** The raw business request (even a single sentence is enough to start)

**Optional:** Vendor documentation, pricing, integration specs, API docs, architect notes, email threads, meeting notes.

Documents can be pulled directly from SharePoint (enterprise knowledge base) and OneDrive (working documents) via Microsoft Graph API.

**How personas drive this step:**

Before any assessment begins, Preflight asks: *"What would each board member want to know before they can even open their mouth?"*

Each persona's `domain` and `constraints` fields generate targeted discovery queries:

| Persona | Auto-generates query for |
|---------|--------------------------|
| Thomas (Application) | ArchiMate: existing application components in this capability space, overlaps, lifecycle status |
| Lena (Integration) | ArchiMate: serving/flow/triggering relationships, interfaces, data flows |
| Jan (Infrastructure) | TOPdesk: related CIs, hosting patterns, asset relationships, DR status |
| Victor (Security) | TOPdesk: open security risks, compliance flags, pending pen test findings |
| Nadia (Risk) | TOPdesk: GRC entries, regulatory flags, vendor due diligence status |
| CMIO | ArchiMate: clinical application components, HL7v2/FHIR/DICOM interfaces, Cloverleaf routing, JiveX, Digizorg flows |
| Aisha (Data) | ArchiMate: data objects, data flows. TOPdesk: DPIAs, data processing agreements |
| Marcus (Chief) | SharePoint: previous ADRs for similar proposals, architecture principles |
| Sophie (Business) | SharePoint: strategy documents, capability maps, related business cases |
| Thomas (Application) | LeanIX: application lifecycle status, technology risk, business criticality |

Each persona's domain keywords drive **specific** queries. If Manufacturing & OT isn't relevant, Erik's queries don't run.

Output: **Landscape Context Brief** — injected into every persona's `history` field via `injectLandscapeContext()` before assessment begins.

### Step 1 — Classify (Persona Routing)

Lightweight LLM call (light tier) to categorize:

- **Type**: new-application / infrastructure-change / integration / data-platform / vendor-selection / clinical-system / manufacturing-ot / rnd-engineering / ai-ml / decommission
- **Impact level**: low / medium / high / critical
- **Regulatory triggers**: patient data → CMIO + FG-DPO activate. Export control → Petra activates. OT boundary → Erik activates. Personal data → Aisha + Nadia activate.

**Classification quality assurance:**

Step 1 classification is a single LLM call that determines the entire downstream pipeline. A misclassification cascades: a clinical system classified as `infrastructure-change` skips CMIO, FG-DPO, and PO entirely.

Mitigations:
- Rule-based overrides for known patterns (patient data keywords always trigger CMIO regardless of classification)
- Hard triage floors (clinical-system cannot be fast-tracked)
- Confidence scoring — below threshold, flag for architect review before proceeding
- Dual classification for high-stakes: two independent calls, flag disagreements

### Step 2 — Retrieve (Persona-Scoped Knowledge)

Each selected persona's `domain` field becomes a RAG query scope. Retrieval is **per-persona**, not global:

| Selected Persona | Retrieves |
|------------------|----------|
| Victor (Security) | Security policies, zero-trust standards, threat modeling templates, SBOM requirements |
| Nadia (Risk) | Regulatory matrices, risk appetite definitions, third-party assessment checklists |
| Thomas (Application) | Tech radar, lifecycle policies, SaaS evaluation criteria, vendor viability thresholds |
| Lena (Integration) | API standards, event-driven patterns, integration SLAs, coupling risk frameworks |
| CMIO | Clinical system policies, FHIR compliance requirements, MDR/IVDR software classification |
| Aisha (Data) | Data classification scheme, GDPR processing rules, DPIA templates, EU AI Act risk tiers |

Each persona gets **its own context bundle**. Victor doesn't need PLM integration standards. Petra doesn't need FHIR compliance rules.

### Step 3 — Assess (Persona Evaluation)

#### Fast Mode — Batched PERSPECTIVES (single LLM call)

For standard intake triage. All selected perspectives in one prompt:

```
## Perspectives
- **cio** (CIO — Strategy & Investment): IT strategy, budget justification, TCO...
- **chief** (Chief Architect — Coherence): target architecture fit, capability map...
- **security** (Security Architecture — VETO): STRIDE, zero trust, IAM design...

## Proposal
[business request + landscape brief + vendor docs]

## Retrieved Context
[per-persona knowledge bundles from Step 2]

## Task
Rate this proposal from EACH perspective.
Use: approve, conditional, concern, block, na

Output format:
[1] cio:conditional chief:approve security:concern ...

For each non-approve rating, add one line:
cio: [reason in one sentence]
security: [reason in one sentence]
```

Parsed by `parseAssessmentRatings()`. Aggregated by `determineTriageLevel()`.

#### Deep Mode — simulatePanel() (per-persona LLM calls)

For high-impact proposals. Uses full `PERSONAS` array with OpenClaw's `simulatePanel()`:

```javascript
const result = await simulatePanel(
  selectedPersonas,
  {
    description: 'Digital Pathology from Sysmex — whole slide imaging...',
    decision: 'Acquire and integrate into clinical workflow',
    context: vendorDocs + landscapeBrief + retrievedKnowledge,
  },
  { interactionRounds: 1, requireDissent: true }
);
```

Each persona responds in character with:
1. **Initial reaction** — how they feel about this
2. **Strongest objection** — what could kill it from their perspective
3. **Hidden concern** — what they're thinking but won't say in the meeting
4. **Conditions for approval** — what they need to say yes

Optional interaction round: personas see each other's reactions and respond.

Then synthesis: predicted outcome, coalition map, top 3 risks, recommended actions.

| Impact | Mode | Why |
|--------|------|-----|
| Low | Fast (batched) | Quick triage, single call |
| Medium | Fast (batched) | Standard review, efficient |
| High | Deep (panel) | Full stakeholder simulation |
| Critical | Deep (panel) + 2 interaction rounds | Maximum scrutiny |

### Step 4 — Challenge (Authority Personas Act)

**4a. Security Veto Check (Victor)**

If Victor blocks: pipeline flags `SECURITY VETO`. Victor's conditions become mandatory. Output shaped as rejection with remediation path. Draft requires sign-off from real security architect.

**4b. Risk Escalation Check (Nadia)**

If Nadia blocks or risk exceeds appetite: pipeline flags `RISK ESCALATION`. Board treatment auto-upgrades to deep review. Draft requires sign-off from real compliance officer.

**4c. FG/DPO Lawfulness Determination**

If FG determines processing is unlawful: pipeline flags `FG DETERMINATION — processing is unlawful in current form`. This is NOT a veto that can be escalated. It is a legal determination under AVG Article 38(3). Draft determination requires sign-off from real FG before it becomes binding.

**4d. Red Team Pre-Mortem (Raven)**

Triggers for high/critical impact when Steps 4a-4c did not block. Raven reviews **the assessments themselves**:
- What did the other personas miss?
- Where did they agree too easily? (groupthink detection)
- What assumptions are they all sharing that might be wrong?
- Pre-mortem: it's 12 months later, this failed. What did nobody flag?

### Step 5 — Output (Architecture Products)

Every finding is attributed to the persona that raised it. The board reads named positions from known roles.

Products generated based on what the assessment triggers (see product selection logic in PREFLIGHT.md). All products bilingual (NL/EN). Language is set per assessment. Templates: see [templates/](templates/).

**Output deduplication**: When multiple personas raise the same concern (e.g., 5 personas say "encrypt the data"), Step 5 synthesis merges overlapping findings into a shared consensus section, then presents unique per-persona findings separately. This prevents noise without losing signal.

---

## Prompt Engineering Strategy

### System Prompt Structure

Each persona's system prompt follows this template:

```
You are simulating {role} on the Enterprise Architecture Board of a Dutch hospital.

Your name is {name}.

## What You Care About
{incentives}

## Your Hard Lines
{constraints}

## Your Domain Expertise
{domain}

## Current Landscape Context
{history — injected at runtime via injectLandscapeContext()}

## Your Task
Evaluate the following proposal from your specific perspective.
You must rate it: approve / conditional / concern / block

For conditional/concern/block, state:
- Your specific finding (grounded in the retrieved context, cite sources)
- Your conditions for approval (actionable, measurable)
- What you would need to see to change your rating

IMPORTANT: You are generating a DRAFT assessment. A real {role} will review your output.
Do not cite regulatory articles or standards unless they appear in the retrieved context below.
If you are unsure whether a specific regulation applies, say so — do not fabricate references.
```

### Hallucination Mitigation

The most dangerous failure: a persona cites a regulation that doesn't exist, and the architect trusts it because the rest of the output looks authoritative.

**Grounding verification pipeline:**

1. **Constrained citation**: Personas are instructed to only cite sources present in their retrieved context bundle. The prompt explicitly says: "Do not cite regulatory articles unless they appear in the retrieved context."
2. **Post-generation citation check**: After each persona assessment, extract all regulatory references (NEN ####, AIVG Article ##, ISO #####). Verify each exists in the knowledge base. Flag unverifiable citations: "⚠ Unverified reference: NEN 7510 A.12.4 — not found in knowledge base. Verify before relying on this finding."
3. **Source linking**: Each finding in the output includes a source reference back to the specific knowledge base chunk that informed it, enabling the architect to verify.

### Prompt Injection Defense

Vendor documents and business requests are untrusted input. A malicious document could contain prompt injection text designed to influence persona assessments.

**Mitigations:**
1. **Input isolation**: Parsed document content is placed in a clearly delimited section of the prompt, separate from system instructions. Documents are quoted, not injected as instructions.
2. **NeMo Guardrails**: Input rails scan for prompt injection patterns in parsed documents before they reach the LLM. Output rails verify persona responses match expected structure.
3. **Document sanitization**: The parsing pipeline strips executable content, embedded scripts, and known injection patterns before producing Markdown output.

---

## ArchiMate Parser

### Scope

The `.archimate` XML parser traverses:

**Elements** (by layer):
- Business: Business Function, Business Process, Business Service, Business Object, Business Role
- Application: Application Component, Application Function, Application Interface, Application Service, Data Object
- Technology: Node, Device, System Software, Technology Service, Artifact

**Relationships** (all 12 ArchiMate types):
- Structural: Composition, Aggregation, Assignment, Realization
- Dependency: Serving, Access, Influence
- Dynamic: Triggering, Flow
- Other: Specialization, Association

**Traversal depth**: Direct relationships for standard queries. Multi-hop traversal (2-3 levels) for cascade analysis in BIA. Configurable per query type.

### Hospital Model vs. ZiRA Model

Both the hospital's `.archimate` model and ZiRA's reference model are loaded. When they conflict:
- Hospital model is authoritative for "what exists"
- ZiRA model is authoritative for "what should exist"
- Conflicts are surfaced: "ZiRA says bedrijfsfunctie X should be served by applicatiefunctie Y. Your model shows it served by Z."

---

## Document Parsing Pipeline

Two tiers, distinct purposes:

```
Document in (PDF/DOCX/PPTX/XLSX/scanned)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  PDF PRIMARY: OpenDataLoader-PDF (self-hosted)        │
│  Tagged-PDF + bounding boxes + tables + OCR + formulas│
│  100% local processing — no API calls, data never     │
│  leaves hospital. Apache 2.0. JVM runtime (Java 11+). │
│                                                      │
│  PDF FAST PATH: PyMuPDF                               │
│  Fast text extraction for simple PDFs.                │
│                                                      │
│  OFFICE: MarkItDown                                   │
│  DOCX / PPTX / XLSX.                                  │
│                                                      │
│  GENERAL: Unstructured.io (self-hosted)               │
│  HTML / email / misc; batch chunking + hierarchy.     │
│                                                      │
│  SCANNED: Azure AI Document Intelligence              │
│  OCR fallback for image-only PDFs (hospital Azure).   │
└──────────────────────────────────────────────────────┘
```

**Why OpenDataLoader-PDF as PDF primary**: 100% local processing matches NEN 7510 / AVG data-residency constraints; per-element bounding boxes provide source provenance for persona findings (page + coordinates attached to every PSA/ADR claim); tagged-PDF + table + formula extraction covers vendor docs, ZiRA PDFs, and regulatory specs in one tool. Trade-off: JVM dependency in the container (accepted; sidecar container or layered JRE base image).

**LlamaParse excluded**: SaaS-only; incompatible with hospital data residency without routing proposals through a third party. Capabilities replaced by OpenDataLoader-PDF (tables, structure) + LLM post-processing for vendor-claim analysis.

**Routing logic**: Step 1 classification drives parser selection by file type and complexity. Complex / tagged / table-heavy PDFs → OpenDataLoader. Simple text PDFs → PyMuPDF. Office → MarkItDown. Everything else → Unstructured.io.

**Data residency**: All primary parsers (OpenDataLoader, PyMuPDF, MarkItDown, Unstructured.io) are self-hosted. Azure AI OCR runs inside the hospital Azure tenant. No component ships documents to external SaaS.

**Fallback chain**:

```
PDF:    OpenDataLoader-PDF → PyMuPDF → Azure AI OCR + LLM post-processing
Office: MarkItDown → Unstructured.io
Other:  Unstructured.io → Azure AI + LLM post-processing
```

No document silently fails. If every tool fails: "⚠ This document could not be parsed. Please provide the content in another format."

**Parse quality validation**:

```python
def validate_parse_quality(original_file, parsed_markdown):
    if parsed_page_count < original_page_count * 0.8:
        flag("Parser may have missed pages")
    if len(parsed_markdown) < original_file_size * 0.1:
        flag("Parsed output suspiciously small")
    if original_has_tables and not parsed_has_tables:
        flag("Tables may not have been extracted")
    if has_numbering_gaps(parsed_markdown):
        flag("Section numbering gap — content may be missing")
```

---

## Embedding Pipeline

Different data types need different chunking strategies and embedding models.

| Data Type | Chunking Strategy | Embedding Model | Why |
|-----------|-------------------|-----------------|-----|
| **ArchiMate models** | Object-based (element + relationships) | Voyage-3-Large | Preserves graph structure. "Application X serves Business Function Y via Interface Z" stays together. |
| **Vendor docs (PDF)** | Hierarchical (parent-child) | BGE-M3 (multilingual) | Sections → subsections → details. Multilingual (NL/EN/DE). |
| **ZiRA / AIVG / NEN specs** | Contextual enrichment (LLM-prefixed) | Voyage-3-Large | Dense regulatory text. LLM generates context prefix before embedding to ground the vector. |
| **Excel / tables** | Row-wise Markdown | MarkItDown + Gemini 2.0 | Per-row with column headers repeated. Table-aware context. |

**Data residency for embedding models**: Voyage-3-Large and Gemini 2.0 are cloud APIs by default. For proposals containing patient data or sensitive content, embeddings must use self-hosted models or the data must be stripped of identifiable information before embedding. This is a deployment-time configuration.

### Abstraction Layer

The embedding and vector store layers follow the same abstraction pattern as the LLM router:

```python
class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str], opts: EmbedOpts) -> list[Vector]: ...

class VectorStoreClient(Protocol):
    async def upsert(self, vectors: list[Vector], metadata: list[dict]) -> None: ...
    async def search(self, query: Vector, filters: dict, top_k: int) -> list[Result]: ...
```

Switching from Milvus to pgvector or from Voyage-3-Large to another model is a configuration change, not a code change.

### Milvus Indexing Architecture (Phase 2+)

Dual collection:

```
Collection 1: DENSE (semantic vectors)
  ├── Voyage-3-Large vectors (ArchiMate, specs)
  ├── BGE-M3 vectors (vendor docs)
  └── Gemini 2.0 vectors (tables)

Collection 2: SPARSE (BM25 keyword vectors)
  └── Exact term matching for ArchiMate IDs, NEN/ISO control numbers,
      AIVG article references, ZiRA bedrijfsfunctie names

Both collections carry metadata:
  source_type, source_file, persona_relevance, language, parent_chunk_id, classification
```

**Hybrid retrieval** (Step 2): Semantic search + keyword search → Reciprocal Rank Fusion → persona filter → parent expansion.

**Phase 1**: pgvector in PostgreSQL. Single collection. No sparse index. Sufficient for validation. Milvus added when retrieval quality data justifies the operational complexity.

---

## Authentication & Authorization

### AuthN: Microsoft Entra ID via OIDC

The hospital's existing identity provider. No separate Preflight accounts.

### AuthZ: OAuth 2.1 + Two-Layer Model

**Layer 1 — RBAC:**

| Role | Can do |
|------|--------|
| `requestor` | Submit requests. View own status. |
| `architect` | Run assessments. View results. Upload documents. |
| `lead-architect` | Override persona recommendations with documented rationale. Approve fast-track. |
| `board-member` | View all assessments routed to board. Mark findings useful/missed/wrong. |
| `board-chair` | Mark assessments as approved/rejected. Record decisions. |
| `chief-architect` | Manage personas, knowledge base, tech radar. View all assessments. |
| `cio` | View all assessments. View dashboards. |
| `compliance-officer` | Access audit trail. View all assessments (read-only). Export for audit. |
| `fg-dpo` | Access audit trail. View DPIAs. Confirm FG determinations. |
| `admin` | Manage roles, integrations, configuration. No assessment content access by default. |

Roles map to Entra ID groups.

**Layer 2 — ABAC (content-driven):**

| Policy | Condition | Effect |
|--------|-----------|--------|
| Patient data restriction | Aisha classifies `bijzondere persoonsgegevens` in Step 3 | Only `clinical-access` roles see full assessment |
| Export control restriction | Petra flags `export-controlled` | Only `export-clearance` roles see full assessment |
| Vendor-confidential | Marked at intake | Only assigned architect + board |
| Board-only findings | Red Team (Raven) findings in Step 4 | Board + chief architect only |
| Compliance escalation | Nadia triggers escalation | Auto-grants compliance-officer and fg-dpo access |

---

## Audit Trail & Compliance Logging

### Regulatory Requirements

| Framework | What it requires |
|-----------|-----------------|
| **NEN 7513** | Log all access to patient-related data: who, what, when, from where, which authorization |
| **NIS2** | Log security events, support incident detection, forensic analysis |
| **MDR** | Traceability from requirement through assessment to decision |
| **AVG/GDPR** | Log processing activities, demonstrate accountability |

### Schema

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type      TEXT NOT NULL,        -- auth, authz, assessment, persona, veto, ...
    action          TEXT NOT NULL,        -- created, accessed, denied, overridden, ...
    actor_id        TEXT NOT NULL,        -- Entra ID user principal
    actor_role      TEXT NOT NULL,        -- RBAC role at time of action
    resource_type   TEXT,
    resource_id     UUID,
    assessment_id   UUID,
    details         JSONB,
    classification  TEXT,                 -- public, confidential, patient-data
    source_ip       INET,
    user_agent      TEXT,
    previous_hash   TEXT,                 -- SHA-256 of previous entry (hash chain)
    entry_hash      TEXT NOT NULL
);

-- Append-only: no UPDATE or DELETE allowed
-- Enforced via PostgreSQL RLS + revoked permissions
```

### SIEM Integration

Security events stream to hospital SIEM in real-time via CEF/syslog:
- Failed authentication, unauthorized access, data classification changes, configuration changes, system errors

### Persona Versioning

When persona incentives/constraints are tuned (Phase 5), versions are tracked. Each assessment records which persona version produced each finding. Required for MDR traceability — reproducing a previous assessment requires the exact persona configuration.

---

## Testing & Validation Strategy

### Tier 1: Deterministic Components — Standard Testing

| Component | Test Type | Failure = |
|-----------|-----------|-----------|
| Routing logic (`selectRelevant()`) | Unit | Wrong personas consulted |
| ABAC policies | Unit | Data exposure |
| RBAC enforcement | Integration | Unauthorized access |
| Audit trail (hash chain) | Integration | Compliance failure |
| ArchiMate parser | Unit | Wrong landscape context |
| BIV scoring aggregation | Unit | Wrong risk classification |
| Triage logic | Unit | Wrong board routing |
| Product selection | Unit | Missing products |
| i18n (NL/EN) | Unit | Broken output |
| Document parsing router | Unit | Wrong parser, silent failure |

### Tier 2: Non-Deterministic — Evaluation Frameworks

**2a. Reference Scenario Benchmark**: 10-15 reference scenarios with known expert assessments. Run Preflight, compare, score per persona (completeness, accuracy, grounding, usefulness, blind spots). Track over time to detect persona drift.

**2b. Retrieval Relevance Testing**: Per reference scenario, define expected knowledge chunks per persona. Alert on missing expected chunks, irrelevant chunks, and cross-contamination.

**2c. BIV Inflation Detection**: Track distribution. Alert if >60% Hoog (conservative bias) or >60% Laag (dangerous leniency). Track board override rate.

**2d. Shadow Assessment**: First 3 months — run alongside existing manual process. Compare Preflight triage with board's actual treatment. Target: >80% agreement. **Kill metric: false fast-track >10% after 3 months → stop and reassess.**

**2e. Stale Knowledge Detection**: Weekly checks against source systems. Block assessment if critical knowledge (ArchiMate model, NEN 7510) is stale.

### Tier 3: End-to-End Scenario Tests

Full pipeline (Steps 0-5) on reference scenarios. Run on every PR.

---

## Repository Structure

```
EA-Council/
├── PREFLIGHT.md                       # Product document
├── ARCHITECTURE.md                    # This document
├── DIGITAL-PATHOLOGY.md               # Worked example
├── README.md                          # Quick start, CLI commands, project overview
├── CLAUDE.md                          # Claude Code guidance
├── personas/
│   └── ea-council-personas.mjs        # 22 MiroFish personas + selectRelevant() + routing
├── templates/                         # Architecture product templates (Jinja2, NL/EN)
│   ├── psa.md
│   ├── adr.md
│   ├── clinical-impact.md
│   ├── process-impact.md
│   ├── vendor-assessment.md
│   ├── dpia.md
│   ├── bia-biv.md
│   ├── integration-design.md
│   ├── network-impact.md
│   ├── security-assessment.md
│   ├── nfr-specification.md
│   ├── eu-ai-act.md
│   ├── operational-readiness.md
│   ├── roadmap-impact.md
│   ├── tech-radar-update.md
│   └── decommission-checklist.md
├── src/preflight/                     # Python backend (package-based)
│   ├── api/                           # FastAPI REST API
│   ├── archimate/                     # ArchiMate XML parser
│   ├── auth/                          # AuthN (Entra ID), AuthZ (RBAC+ABAC), Audit, Guardrails
│   ├── citation/                      # Citation processor (verify/link/remove)
│   ├── classify/                      # Heuristic + LLM classification
│   ├── cli/                           # Click CLI (assess, full-assess, ingest, quick-scan)
│   ├── db/                            # SQLAlchemy models, session, DDL
│   ├── embedding/                     # Embedding router, contextual retrieval, pipeline
│   ├── guardrails/                    # NeMo Guardrails + Colang config
│   ├── integrations/                  # TOPdesk, LeanIX, Graph connectors
│   ├── llm/                           # LLM client (Ollama, NIM), router, parser
│   ├── model/                         # Domain models
│   ├── models/                        # SQLAlchemy ORM models
│   ├── parsing/                       # Document parsers (PDF, DOCX, MD, .archimate)
│   ├── pipeline/                      # Orchestrator, pipeline, quickscan
│   ├── retrieval/                     # pgvector store, enrichment, reranker
│   └── synthesis/                     # Document generation (Jinja2), diagrams
├── synthesis/                         # JavaScript synthesis modules (original MiroFish)
│   ├── archimate.mjs                  # ArchiMate XML synthesis
│   ├── clarification.mjs             # Clarification logic
│   ├── diagrams.mjs                  # Diagram generation
│   ├── engine.mjs                    # Core synthesis engine
│   └── pipeline.mjs                  # Pipeline orchestration
├── scripts/                           # Utility scripts
│   ├── seed.py                        # Database seeding
│   └── init-db.sql                    # PostgreSQL initialization (pgvector)
├── alembic/                           # Database migrations
├── tests/                             # pytest test suite
├── experiment/                        # QA ground truth, experiment configs
├── novius/                            # NAR reference architecture research
├── docker-compose.yml                 # PostgreSQL + pgvector
├── pyproject.toml                     # Python project config (deps, CLI entry)
├── Makefile                           # Dev tasks (install, test, lint, migrate, seed)
└── preflight                          # Shell wrapper for CLI
```

---

## What Runs Where

- LLM via NIM containers on GPU infrastructure (on-prem or cloud), or Ollama for local dev
- Vector store: pgvector in Phase 1, Milvus in Phase 2+
- PostgreSQL for audit trail + assessment history
- FastAPI service on standard compute
- Next.js frontend on standard compute (or Vercel/Azure Static Web Apps)
- Microsoft Entra ID for authentication (hospital's existing provider)
- No Power Automate. No Copilot Studio. No connector licensing. (See justification in PREFLIGHT.md.)

---

*Full deployment architecture, capacity planning, DR plan, and network topology to be designed in Phase 2 when infrastructure requirements are validated by Phase 1 usage data.*
