# Preflight

**"Run it through Preflight."**

An EA intake and pre-assessment tool that does the analytical homework — from the moment the business asks for something, through to a board-ready package. It doesn't replace the EA board. It prepares the EA board.

---

## What It Is

Preflight takes a business request — as raw as "we want Digital Pathology from Sysmex" — and runs it through 17 MiroFish personas representing the full EA board plus security, privacy, and compliance officers: CIO, CMIO, Chief Architect, 7 domain architects, Security (veto), CISO, ISO, Risk & Compliance (escalation), FG/DPO (independent — cannot be overruled), Privacy Officer, and Red Team. The personas don't just evaluate — they drive every step of the pipeline: what to look up, what to retrieve, what to flag, how to assess, where to challenge.

The architect reviews, adjusts, adds judgment, and brings a strong package to the board — or fast-tracks it without a board session at all.

## What It Is Not

- Not an EA board simulator
- Not a decision-maker
- Not a multi-agent system pretending to deliberate
- Not a Copilot Studio chatbot

## The Problem

Today, when the business says "we want X":

1. An architect gets assigned
2. They spend days/weeks gathering context — what does it do, what does it connect to, where does it sit in the landscape, what data does it handle, does it overlap with something we have
3. They write up an initial assessment
4. It goes to the board
5. The board asks questions the architect didn't think to cover
6. Back to step 2

The cycle time from business request to architectural decision is weeks to months. Most of that time is spent on structured, repeatable analytical work — not judgment.

## Core Concept: Persona-Driven Pipeline

The 17 MiroFish personas are not bolted onto Step 3. They are the pipeline. Every step is shaped by what the relevant personas would ask, look for, flag, and challenge.

```
┌───────────────────────────────────────────────────────────┐
│                        PREFLIGHT                           │
│                                                           │
│  Personas loaded: ea-council-personas.mjs                 │
│  17 roles × 6 fields (role, name, incentives,             │
│  constraints, domain, history)                            │
│                                                           │
│  ┌───────────┐  Personas ask:                             │
│  │ Step 0    │  "What would each role want to know        │
│  │ INGEST    │   before they can even begin to assess?"   │
│  │           │  → drives ArchiMate/TOPdesk queries        │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas determine:                       │
│  │ Step 1    │  "Who needs to be in the room for this?"   │
│  │ CLASSIFY  │  → selectRelevant() picks 5-9 personas    │
│  │           │  → regulatory triggers activate CMIO,      │
│  │           │    Risk, Security automatically            │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas drive:                           │
│  │ Step 2    │  "What does each selected persona need     │
│  │ RETRIEVE  │   to see to do their job?"                 │
│  │           │  → each persona's domain keywords guide    │
│  │           │    RAG retrieval + targeted API queries     │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas evaluate:                        │
│  │ Step 3    │  Two modes available —                     │
│  │ ASSESS    │  Fast: batched PERSPECTIVES, single call   │
│  │           │  Deep: simulatePanel(), per-persona calls  │
│  │           │       + interaction rounds + synthesis      │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas with authority act:              │
│  │ Step 4    │  Security (Victor) → VETO if block         │
│  │ CHALLENGE │  Risk (Nadia) → ESCALATE if block          │
│  │           │  Red Team (Raven) → pre-mortem on the      │
│  │           │    assessments themselves                   │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas shape:                           │
│  │ Step 5    │  determineTriageLevel() aggregates          │
│  │ OUTPUT    │  persona ratings → board treatment          │
│  │           │  Each persona's findings become a named    │
│  │           │  section in the output: "Victor (Security): │
│  │           │  BLOCK — no STRIDE threat model provided"  │
│  └───────────┘                                            │
└───────────────────────────────────────────────────────────┘
```

## The Personas

Defined in `personas/ea-council-personas.mjs`. Compatible with OpenClaw's `simulatePanel()`.

| Persona | Name | Type | Special Authority |
|---------|------|------|-------------------|
| Chief Information Officer | CIO | Executive | Budget & strategy gate |
| Chief Medical Information Officer | CMIO | Executive | Clinical safety gate |
| Chief Architect | Marcus | Orchestrator | Final recommendation |
| Business Architecture | Sophie | Domain | Strategy alignment |
| Application Architecture | Thomas | Domain | Portfolio & tech radar |
| Integration Architecture | Lena | Domain | Coupling & API standards |
| Technology & Infrastructure | Jan | Domain | Hosting, DR, operations |
| Data & AI Architecture | Aisha | Domain | Data governance, EU AI Act |
| Manufacturing & OT | Erik | Domain | Production continuity, IEC 62443 |
| R&D & Engineering Design | Petra | Domain | IP protection, export control |
| Security Architecture | Victor | Cross-cut | **VETO power** |
| CISO | CISO | Cross-cut | Strategic security risk acceptance |
| Information Security Officer | ISO-Officer | Cross-cut | NEN 7510 ISMS, operational security |
| Risk & Compliance | Nadia | Cross-cut | **ESCALATION power** |
| FG / Data Protection Officer | FG-DPO | Cross-cut | **INDEPENDENT — cannot be overruled** |
| Privacy Officer | PO | Cross-cut | Privacy by design, DPIA execution |
| Red Team | Raven | Cross-cut | Challenge only |

Each persona carries: `role`, `name`, `incentives`, `constraints`, `domain`, `history` (injected at runtime with landscape data).

## Framework: NemoClaw

Preflight is built on **NemoClaw** — NVIDIA's enterprise AI stack (NeMo, NIM, Guardrails) combined with OpenClaw's patterns (MiroFish personas, simulatePanel protocol). The framework, not a specific model.

### LLM Strategy: Route by Reasoning Demand

The pipeline does not use one model for everything. Different steps have different reasoning demands. The LLM layer is a router that dispatches to the right tier:

```
┌─────────────────────────────────────────────┐
│               LLM Router                     │
│                                             │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Light   │  │  Strong  │  │ Frontier  │  │
│  │ Steps    │  │ Steps    │  │ Steps     │  │
│  │ 0,1,2,5 │  │ 3        │  │ 4         │  │
│  └─────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────┘
```

| Tier | Used by | Requirement | Examples |
|------|---------|-------------|---------|
| **Light** | Steps 0, 1, 2, 5 — query generation, classification, retrieval scoping, output formatting | Fast, cheap, good instruction following | Small self-hosted model via NIM, Ollama for local dev |
| **Strong** | Step 3 — multi-perspective structured assessment, simulatePanel() role-play | Nuanced reasoning, stays in character, structured output | Mid-size self-hosted model via NIM |
| **Frontier** | Step 4 — adversarial review, finding what all other personas missed | Best reasoning available — this is where model quality matters most | Frontier API call (when stakes justify cost), or best available self-hosted |

Cost goes where it matters: 80% of calls hit the light tier (near zero cost). The frontier tier only fires for high/critical impact proposals in Step 4.

**Phase 1 approach:** Start with a single model for all tiers. Instrument every step with quality metrics. Split the routing when you have data on where quality matters vs. where it's wasted. Don't over-engineer the routing before you know which models you're running.

```python
class LLMRouter:
    light: LLMClient     # Steps 0, 1, 2, 5
    strong: LLMClient    # Step 3
    frontier: LLMClient  # Step 4

class LLMClient(Protocol):
    async def call(self, system: str, user: str, opts: CallOpts) -> LLMResponse: ...
```

Behind each client: NIM endpoint, Ollama, or external API. The pipeline doesn't care. The personas don't care. `simulatePanel()` calls `router.strong.call()` and gets text back.

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | | |
| LLM | LLMRouter (pluggable — NIM, Ollama, API) | Tiered reasoning engine |
| Personas | MiroFish (ea-council-personas.py) | Drive every pipeline step |
| Orchestration | Python / FastAPI | Request flow, API layer |
| Knowledge store | Milvus | RAG over policies, principles, standards, tech radar |
| Embedding | Tiered: Voyage-3-Large, BGE-M3, LlamaParse + Gemini 2.0 | Data-type-specific chunking + embedding (see below) |
| Guardrails | NeMo Guardrails | Input/output filtering for sensitive proposal data |
| Document parsing | Tiered parsing pipeline (see below) | PDF, DOCX, PPTX, XLSX, scanned docs extraction |
| AuthN | Microsoft Entra ID (OIDC) | SSO, identity verification, integrates with hospital identity provider |
| AuthZ | OAuth 2.1 + RBAC/ABAC policy engine | Token-based authorization with role and attribute policies |
| Audit trail | Append-only log (PostgreSQL) + SIEM integration | Immutable record of every assessment, access decision, and system event |
| **Frontend** | | |
| Web UI | Next.js + shadcn/ui + Tailwind | Architect-facing interface — bilingual NL/EN |
| Design system | UI UX Pro Max | Design system generation (colors, typography, patterns, style) |
| Design quality | Impeccable | UI audit, critique, polish — enforces quality on implementation |
| **Integrations** | | |
| ArchiMate (Archi) | .archimate XML parser | Application landscape, capabilities, interfaces, tech stack, relationships |
| TOPdesk | REST API | CMDB, assets, CIs, change records, open risks, GRC |
| SharePoint | Microsoft Graph API | Architecture policies, standards, board decisions, reference docs |
| OneDrive | Microsoft Graph API | Vendor docs, data sheets, proposal attachments, architect notes |

### Authentication & Authorization

**AuthN: Who are you?**

Microsoft Entra ID via OIDC. The hospital's existing identity provider. Architects, board members, compliance officers, and business requestors authenticate with their hospital credentials. No separate Preflight accounts.

**AuthZ: What can you do?**

OAuth 2.1 provides the token framework (scopes, claims). On top of that, a two-layer authorization model:

**Layer 1 — RBAC (Role-Based Access Control)**

| Role | Can do |
|------|--------|
| `requestor` | Submit intake requests. View own request status. |
| `architect` | Run assessments on assigned proposals. View results. Upload documents. |
| `lead-architect` | Everything architect can do + override persona recommendations with documented rationale. Approve fast-track assessments. |
| `board-member` | View all assessments routed to the board. Mark sections as useful/missed/wrong (feedback). |
| `board-chair` | Everything board-member can do + mark assessments as board-approved or rejected. |
| `chief-architect` | Everything lead-architect can do + manage personas, knowledge base, tech radar. View all assessments. |
| `cio` | View all assessments. View aggregated metrics and dashboards. |
| `compliance-officer` | Access audit trail. View all assessments (read-only). Export for audit purposes. |
| `fg-dpo` | Access audit trail. View data processing assessments (DPIAs). Respond to betrokkene requests. |
| `admin` | Manage roles, integrations, system configuration. No access to assessment content by default. |

Roles map to Entra ID groups. No Preflight-specific user management.

**Layer 2 — ABAC (Attribute-Based Access Control)**

RBAC handles the base layer. ABAC handles the sensitive cases — where the *content* of the assessment determines who can see it:

| Policy | Condition | Effect |
|--------|-----------|--------|
| Patient data restriction | Aisha (Data) classifies proposal as containing `persoonsgegevens` or `bijzondere persoonsgegevens` in Step 3 | Only roles with `clinical-access` attribute can view full assessment. Others see redacted version. |
| Export control restriction | Petra (R&D) flags `export-controlled` IP in Step 3 | Only roles with `export-clearance` attribute can view. |
| Vendor-confidential | Proposal marked as `vendor-confidential` at intake | Only assigned architect + board members can view. Requestor sees status only. |
| Board-only findings | Red Team (Raven) findings in Step 4 | Board members + chief architect only. Not visible to requestor. |
| Compliance escalation | Nadia triggers escalation in Step 4 | Automatically grants `compliance-officer` and `fg-dpo` access to this assessment. |

**How it flows:**

```
1. User authenticates → Entra ID → OIDC token with roles (claims)
2. User requests action → OAuth 2.1 token with scopes
3. RBAC check: does this role allow this action?
4. ABAC check: does the assessment content restrict this user?
   (data classification from Step 3 feeds into access policy)
5. NEN 7513 log: record access decision (allow/deny, who, what, when, why)
```

**NEN 7513 Compliance:**

Every authorization decision is logged per NEN 7513 requirements:
- **Wie**: authenticated user identity
- **Wat**: which assessment / which section accessed
- **Wanneer**: timestamp
- **Waarvandaan**: source IP, device
- **Welke autorisatie**: which role + which ABAC policy applied
- **Waarom**: access justification (derived from role assignment + request context)

Logs are append-only, tamper-proof, retained per hospital retention policy. Accessible only to `compliance-officer` and `fg-dpo` roles.

### Audit Trail & Compliance Logging

Preflight operates in a regulated environment. The audit trail isn't just a log — it's a compliance instrument that serves multiple regulatory frameworks simultaneously.

**Regulatory requirements driving the audit trail:**

| Framework | What it requires from Preflight |
|-----------|--------------------------------|
| **NEN 7513** | Log all access to patient-related data: who, what, when, from where, which authorization. Tamper-proof, auditable, retained per hospital policy. |
| **NIS2** | As a system supporting essential services (healthcare), Preflight must: log security-relevant events, support incident detection, enable forensic analysis, report significant incidents within 24h/72h. |
| **MDR (Medical Device Regulation)** | If Preflight assesses proposals involving medical device software (SaMD, IEC 62304 Class B/C), the assessment itself becomes part of the device's quality documentation trail. Traceability from requirement through assessment to decision. |
| **AVG/GDPR** | Log processing activities involving personal data. Demonstrate accountability (verantwoordingsplicht). Support data subject access requests (inzageverzoeken). |
| **SOC 2 (Type II)** | If Preflight becomes a shared service: demonstrate continuous control effectiveness over security, availability, processing integrity, confidentiality, and privacy. Requires structured, queryable audit evidence. |
| **SIEM integration** | Security events from Preflight must flow to the hospital's SIEM for correlation with other systems. Failed auth attempts, unauthorized access, data classification events, policy violations. |

**What gets logged:**

| Event Category | Events | Required by |
|---------------|--------|-------------|
| **Authentication** | Login success/failure, token refresh, session start/end | NIS2, SOC 2, SIEM |
| **Authorization** | Access granted/denied, ABAC policy triggered, role check result | NEN 7513, NIS2, SOC 2, SIEM |
| **Assessment lifecycle** | Created, classified, personas selected, assessment started/completed, triage determined | MDR, SOC 2 |
| **Persona output** | Each persona's rating and findings (immutable once generated) | MDR (traceability) |
| **Veto/escalation** | Victor blocks, Nadia escalates, Red Team triggered | MDR, SOC 2 |
| **Data classification** | Aisha classifies data as patient/personal/confidential → triggers ABAC policy | NEN 7513, AVG |
| **Document access** | Which documents were ingested, parsed, embedded — per assessment | NEN 7513 (if patient data), AVG |
| **Board decisions** | Assessment approved/rejected/conditions set by board | MDR, SOC 2 |
| **Architect overrides** | Persona recommendation overridden with rationale | MDR (traceability), SOC 2 |
| **System events** | LLM calls (which tier, latency, token count), parsing failures, embedding errors | NIS2, SOC 2, SIEM |
| **Configuration changes** | Persona updates, knowledge base changes, policy changes, role assignments | NIS2, SOC 2, SIEM |

**Audit log schema:**

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type      TEXT NOT NULL,        -- auth, authz, assessment, persona, veto, data_classification, ...
    action          TEXT NOT NULL,        -- created, accessed, denied, overridden, ...
    actor_id        TEXT NOT NULL,        -- Entra ID user principal
    actor_role      TEXT NOT NULL,        -- RBAC role at time of action
    resource_type   TEXT,                 -- assessment, document, persona, config
    resource_id     UUID,                 -- ID of the affected resource
    assessment_id   UUID,                 -- links to parent assessment (if applicable)
    details         JSONB,               -- event-specific payload (findings, rationale, policy applied)
    classification  TEXT,                 -- public, confidential, patient-data
    source_ip       INET,
    user_agent      TEXT,
    
    -- Tamper protection
    previous_hash   TEXT,                 -- SHA-256 of previous log entry (hash chain)
    entry_hash      TEXT NOT NULL         -- SHA-256 of this entry (computed from all fields + previous_hash)
);

-- Append-only: no UPDATE or DELETE allowed
-- Enforced via PostgreSQL RLS + revoked permissions
-- Hash chain enables tamper detection at query time
```

**Tamper protection:** Each log entry includes a SHA-256 hash of the previous entry, forming a hash chain. Verification queries can detect any modification or deletion. PostgreSQL Row-Level Security + revoked UPDATE/DELETE permissions enforce append-only at the database level.

**Retention:** Configurable per event category. Default minimum per regulatory requirement:
- NEN 7513 access logs: per hospital retention policy (typically 5 years)
- MDR assessment trails: lifetime of the medical device + 10 years
- NIS2 security events: minimum 18 months
- AVG processing logs: as long as processing continues + demonstration period

**SIEM Integration:**

Security-relevant events stream to the hospital's SIEM in real-time:

```
Preflight audit log
    │
    ├── Security events → SIEM (real-time via syslog/CEF or webhook)
    │   - Failed authentication
    │   - Unauthorized access attempts
    │   - Data classification changes
    │   - Configuration changes
    │   - System errors / parsing failures
    │
    └── All events → PostgreSQL (append-only, hash-chained)
        - Full audit trail for compliance queries
        - Accessible via compliance dashboard
```

The SIEM receives structured events in CEF (Common Event Format) or syslog format, compatible with whatever the hospital runs (Splunk, Microsoft Sentinel, QRadar, etc.). Preflight doesn't need to know which SIEM — it pushes to a standard format.

**SOC 2 readiness:**

If Preflight is operated as a shared service (multiple hospitals or departments), the audit trail provides the evidence base for SOC 2 Type II:
- **Security**: auth events, access control enforcement, SIEM integration
- **Availability**: system event monitoring, uptime tracking
- **Processing integrity**: assessment lifecycle tracking, persona output immutability, hash chain verification
- **Confidentiality**: data classification enforcement, ABAC policy logs
- **Privacy**: AVG processing activity logs, DPIA tracking, data subject request handling

**Compliance dashboard (frontend):**

The `compliance-officer` and `fg-dpo` roles get a dedicated view in the Preflight UI:
- Query audit trail by time range, event type, actor, assessment, classification
- Verify hash chain integrity
- Export for external auditors (CSV/JSON)
- Alert on anomalies (unusual access patterns, repeated denials)
- NEN 7513 report generator (who accessed patient-related assessments)
- NIS2 incident timeline view

### Document Parsing Pipeline

Documents flow into Preflight from SharePoint, OneDrive, or direct upload. The parsing pipeline converts them to Markdown (the lingua franca for LLM consumption) using a tiered approach:

```
Document in (PDF/DOCX/PPTX/XLSX/scanned)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│              Document Parsing Pipeline                 │
│                                                      │
│  TWO TIERS:                                          │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │ WORKHORSE: Unstructured.io (self-hosted)       │  │
│  │ General ingestion — all file types, batches,   │  │
│  │ chunking for RAG, maintaining doc hierarchy.   │  │
│  │ Assisted by:                                   │  │
│  │   MarkItDown  — Office docs (DOCX/PPTX/XLSX)  │  │
│  │   PyMuPDF     — Fast PDF text extraction       │  │
│  │   Azure AI    — OCR for scanned docs           │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼───────────────────────────┐  │
│  │ SMART: LlamaParse                              │  │
│  │ AI-powered understanding — when the document   │  │
│  │ needs to be truly understood, not just parsed.  │  │
│  │ Complex tables, cross-references, contract     │  │
│  │ clause extraction, vendor claim analysis.       │  │
│  └────────────────────┬───────────────────────────┘  │
│                       │                              │
└───────────────────────┼──────────────────────────────┘
                        ▼
                  Markdown output → Step 0 (Ingest)
```

**Two tiers, distinct purposes:**

### Workhorse: Unstructured.io (self-hosted)

The backend ingestion engine. Handles everything that comes in — any file type, any batch size, any combination. Self-hosted so data never leaves the hospital.

Unstructured orchestrates the specialist tools as needed:

| Specialist | Role within Unstructured pipeline |
|-----------|-----------------------------------|
| **MarkItDown** | Office docs (DOCX, PPTX, XLSX) — Microsoft-native, outputs clean Markdown |
| **PyMuPDF (fitz)** | Fast text extraction from digital PDFs — vendor data sheets, policies, standards |
| **Azure AI Document Intelligence** | OCR fallback for scanned documents, handwritten annotations, image-heavy PDFs. Stays in hospital Azure tenant. Pre-built contract/invoice models for AIVG compliance checking. |

Unstructured handles: file type detection, routing to the right specialist, chunking output for the RAG embedding pipeline, maintaining document hierarchy (sections, headers, tables), and producing clean Markdown with metadata.

### Smart: LlamaParse

For when the document needs to be *understood*, not just extracted. LlamaParse uses AI to comprehend document structure and meaning — it doesn't just OCR text, it reasons about what the document is saying.

**When Smart mode triggers:**

| Scenario | Why LlamaParse, not just extraction |
|----------|-------------------------------------|
| Vendor contract analysis | Extract specific AIVG-relevant clauses (exit, escrow, liability, SLA) from dense legal text. Understands contract structure. |
| Complex technical specs | Multi-column datasheets with cross-referenced tables, footnotes, conditional specs. Preserves semantic relationships between data points. |
| Architecture documents | Diagrams with embedded text, layered information, cross-references between sections. Understands the logical flow, not just the text. |
| Vendor claims vs. facts | Separates marketing language from verifiable technical claims. Flags assertions that need validation. |
| Regulatory mapping | Maps vendor documentation to specific NEN/ISO/AIVG requirements. Understands which clause answers which compliance question. |

**Routing logic:**

```python
async def parse_document(file_path: str, intent: str) -> ParsedDocument:
    # Smart mode: when AI understanding is needed
    if intent in ('contract_analysis', 'regulatory_mapping', 'vendor_claims'):
        smart_result = await llamaparse.parse(file_path)
        return smart_result
    
    # Workhorse: general ingestion through Unstructured
    # Unstructured auto-routes to MarkItDown/PyMuPDF/Azure AI internally
    workhorse_result = await unstructured.partition(
        file_path,
        strategy='hi_res' if needs_ocr(file_path) else 'fast',
        chunking_strategy='by_title',  # maintain document hierarchy
    )
    return workhorse_result
```

**Who decides which mode?** Step 1 (Classify). When the proposal is classified as `vendor-selection` and vendor contracts are uploaded, Smart mode activates for those contracts. When it's general document ingestion (policies, data sheets, architect notes), Workhorse handles it.

**Output contract (both tiers):** Markdown with:
- Document title and metadata
- Section headers preserved (hierarchy intact)
- Tables converted to Markdown tables
- Images described (alt-text or OCR'd text)
- Page numbers annotated for traceability
- Chunking boundaries marked (for RAG embedding)

Workhorse output feeds into the embedding pipeline for Milvus. Smart output feeds directly into the persona assessments — it's already understood, not just extracted.

### Embedding Pipeline

Parsed documents don't go into Milvus as one blob. Different data types need different chunking strategies and different embedding models — what works for a vendor PDF destroys the structure of an ArchiMate model.

**Four strategies, matched to data type:**

| Data Type | Chunking Strategy | Embedding Model | Why |
|-----------|-------------------|-----------------|-----|
| **ArchiMate models** | Object-based (element + relationships) | Voyage-3-Large | Each ArchiMate element (application component, business function, interface) becomes a chunk with its direct relationships embedded as context. Preserves the graph structure — "Application X *serves* Business Function Y *via* Interface Z" stays together. Voyage-3-Large handles the semantic density of architectural descriptions. |
| **Vendor docs (PDF)** | Hierarchical (parent-child) | BGE-M3 (multilingual) | Vendor docs have sections → subsections → details. Parent chunks hold section summaries, child chunks hold detail. Query retrieves the right detail AND its parent context. BGE-M3 because vendor docs arrive in Dutch, English, and German — multilingual support is non-negotiable. |
| **ZiRA / AIVG / NEN specs** | Contextual enrichment (LLM-prefixed) | Voyage-3-Large | Regulatory and reference architecture text is dense and self-referential. Before embedding, an LLM generates a context prefix: "This chunk describes NEN 7510 control A.12.4 — logging and monitoring requirements for healthcare information systems." The prefix grounds the embedding so retrieval finds the right clause, not a semantically similar but wrong one. Voyage-3-Large captures the nuance. |
| **Excel / tables** | Row-wise Markdown | LlamaParse + Gemini 2.0 | Tables (pricing sheets, comparison matrices, tech radar exports) are converted to per-row Markdown with column headers repeated. LlamaParse handles the structural understanding, Gemini 2.0 embeds with table-aware context. Each row becomes a retrievable unit with its column headers as context. |

**How it flows:**

```
Parsed Markdown (from Document Parsing Pipeline)
    │
    ▼
┌─────────────────────────────────────────┐
│  Chunking Router                         │
│  Detects data type → applies strategy   │
│                                         │
│  .archimate XML  → object-based chunks  │
│  Vendor PDFs     → hierarchical chunks  │
│  ZiRA/AIVG/NEN   → LLM-prefixed chunks │
│  Excel/tables    → row-wise chunks      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Embedding Router                        │
│  Selects model per data type            │
│                                         │
│  ArchiMate / specs → Voyage-3-Large     │
│  Vendor docs       → BGE-M3            │
│  Tables            → Gemini 2.0         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Milvus                                  │
│  Stored with metadata:                  │
│  - source_type (archimate/vendor/zira/  │
│    aivg/nen/table)                      │
│  - source_file                          │
│  - persona_relevance (which personas    │
│    should see this chunk)               │
│  - language (nl/en/de)                  │
│  - parent_chunk_id (for hierarchical)   │
│  - classification (public/confidential/ │
│    patient-data)                        │
└─────────────────────────────────────────┘
```

**Embedding Models — Technical-First:**

Standard general-purpose embeddings miss the nuance of architecture relationships and regulatory terminology.

| Model | Used for | Why |
|-------|----------|-----|
| **Voyage-3-Large** | ArchiMate elements, ZiRA/AIVG/NEN specs | Outperforms general-purpose models on technical documentation and hierarchical relationships. Understands domain-specific terminology. |
| **BGE-M3** (multilingual) | Vendor docs | Multi-vector retrieval + late interaction (ColBERT-style). Critical for catching specific keywords in vendor docs while maintaining semantic understanding. Multilingual: Dutch, English, German. |
| **Gemini 2.0** | Tables (via LlamaParse) | Table-aware context embedding after LlamaParse structural extraction. |

**Matryoshka Embeddings:** Use multi-resolution vectors (available in Voyage-3-Large). Store a smaller vector (256 or 512 dimensions) in Milvus for fast initial filtering, then use the full vector (3072) for final reranking. This gives speed on large knowledge bases without sacrificing precision.

**Contextual Enrichment (the "garbage retrieval" fix):**

Before embedding ZiRA/AIVG/NEN chunks, a light LLM call (light tier from LLMRouter) generates a context prefix:

> "This chunk describes NEN 7510 control A.12.4 — logging and monitoring requirements for healthcare information systems, applicable when clinical systems access patient records."

This prefix is prepended to the chunk before embedding. It grounds the vector so retrieval finds the right regulatory clause, not a semantically similar but wrong one.

**Milvus Indexing Architecture — Dual Collection:**

```
┌─────────────────────────────────────────────────┐
│  Milvus                                          │
│                                                 │
│  Collection 1: DENSE (semantic vectors)          │
│  ├── Voyage-3-Large vectors (ArchiMate, specs)  │
│  ├── BGE-M3 vectors (vendor docs)               │
│  └── Gemini 2.0 vectors (tables)                │
│                                                 │
│  Collection 2: SPARSE (BM25 keyword vectors)     │
│  └── Exact term matching for:                   │
│      - ArchiMate element IDs                    │
│      - Vendor product names / version numbers   │
│      - NEN/ISO control numbers                  │
│      - AIVG article references                  │
│      - ZiRA bedrijfsfunctie names               │
│                                                 │
│  Both collections carry metadata:               │
│  - source_type (archimate/vendor/zira/aivg/     │
│    nen/table)                                   │
│  - source_file                                  │
│  - persona_relevance (which personas should     │
│    see this chunk)                              │
│  - language (nl/en/de)                          │
│  - parent_chunk_id (for hierarchical)           │
│  - classification (public/confidential/         │
│    patient-data)                                │
└─────────────────────────────────────────────────┘
```

**Hybrid Retrieval (Step 2):**

Retrieval combines both collections using **Reciprocal Rank Fusion (RRF)**:

1. **Semantic search** (Collection 1, dense) — "find chunks about security requirements for clinical integration" → catches meaning
2. **Keyword search** (Collection 2, sparse/BM25) — "NEN 7510 A.12.4" → catches exact references
3. **RRF fusion** — merge results, weighted by both semantic relevance and keyword precision
4. **Persona filter** — `persona_relevance` metadata restricts results to the querying persona's domain
5. **Parent expansion** — for hierarchical chunks, pull the parent summary to provide context

This ensures Victor searching for "NEN 7510 logging" gets the exact control (via BM25) plus semantically related controls about audit trails and monitoring (via dense search), all in one query.

**Persona-scoped retrieval (Step 2)** uses the `persona_relevance` metadata field. When Thomas (Application) queries Milvus, he gets ArchiMate application components and tech radar entries. When Nadia (Risk) queries, she gets AIVG clauses and NEN controls. The embedding pipeline tags each chunk at index time so retrieval is fast and precise.

**Re-indexing:** Knowledge base changes trigger re-embedding. ArchiMate model updates (new .archimate file in SharePoint) trigger object-based re-chunking. AIVG/NEN updates trigger contextual re-enrichment. CI job on merge to main for the knowledge/ directory.

### Fallback Chain

If the primary tool for a tier fails or produces poor output, the pipeline falls back:

```
Workhorse tier:
  Unstructured.io (primary)
    → MarkItDown (fallback for Office docs if Unstructured fails)
    → PyMuPDF (fallback for PDFs if Unstructured fails)
    → Azure AI Document Intelligence (fallback for OCR if all local parsers fail)

Smart tier:
  LlamaParse (primary)
    → Azure AI Document Intelligence + LLM post-processing (fallback)
    → Unstructured hi_res + LLM post-processing (fallback)
```

No document should ever silently fail to parse. If every tool in the chain fails, the pipeline flags it to the architect: "This document could not be parsed — please provide the content in another format or paste the relevant sections manually."

### What Runs Where

- LLM via NIM containers on GPU infrastructure (on-prem or cloud), or Ollama for local dev
- Milvus on standard compute
- PostgreSQL for audit trail + assessment history
- FastAPI service on standard compute
- Next.js frontend on standard compute (or Vercel/Azure Static Web Apps)
- Microsoft Entra ID for authentication (hospital's existing identity provider)
- No Power Automate. No Copilot Studio. No connector licensing.

## The Six-Step Flow

### Step 0 — Ingest (Persona-Driven Discovery)

The front door. The architect feeds Preflight:

**Required:**
- The raw business request (even a single sentence is enough to start)

**Optional (the more, the better):**
- Vendor documentation, data sheets, architecture diagrams
- Pricing information, licensing model
- Integration specs, API documentation
- Architect's own notes, concerns, context
- Related email threads, meeting notes

Documents don't need to be uploaded manually. Preflight pulls directly from where they already live:
- **SharePoint**: architecture policies, standards, previous board decisions, reference documentation — the enterprise knowledge base
- **OneDrive**: vendor docs, data sheets, proposal attachments that the architect or business has saved — the working documents

Both via **Microsoft Graph API**. The architect points Preflight at a SharePoint site or OneDrive folder, and it ingests what's there. No copy-paste, no re-uploading what already exists.

**How personas drive this step:**

Before any assessment begins, Preflight asks: *"What would each board member want to know before they can even open their mouth?"*

Each persona's `domain` and `constraints` fields generate targeted discovery queries:

| Persona | Auto-generates query for |
|---------|--------------------------|
| Thomas (Application) | ArchiMate model: existing application components in this capability space, overlaps, lifecycle status |
| Lena (Integration) | ArchiMate model: serving/flow/triggering relationships, interfaces, data flows touching this domain |
| Jan (Infrastructure) | TOPdesk: related CIs, hosting patterns, asset relationships, DR status of connected systems |
| Victor (Security) | TOPdesk: open security risks, compliance flags, pending pen test findings, CI security classification |
| Nadia (Risk) | TOPdesk: GRC entries, regulatory flags, vendor due diligence status |
| CMIO | ArchiMate model: clinical application components, technology interfaces (HL7v2, FHIR, DICOM), integration via Cloverleaf, imaging via JiveX, Digizorg exchange flows |
| Aisha (Data) | ArchiMate model: data objects, data flows. TOPdesk: DPIAs, data processing agreements |
| Marcus (Chief) | SharePoint: previous ADRs for similar proposals, architecture principles, reference architectures |
| Sophie (Business) | SharePoint: strategy documents, capability maps, business cases for related initiatives |
| All selected | OneDrive: vendor docs, data sheets, proposal attachments the architect has saved for this request |

This is not a generic "query everything" approach. Each persona's domain keywords drive **specific** queries. If Manufacturing & OT isn't relevant, Erik's queries don't run.

Output: **Landscape Context Brief** — injected into every persona's `history` field via `injectLandscapeContext()` before assessment begins.

### Step 1 — Classify (Persona Routing)

Lightweight LLM call to categorize the request:
- **Type**: new-application / infrastructure-change / integration / data-platform / vendor-selection / clinical-system / manufacturing-ot / rnd-engineering / ai-ml / decommission
- **Impact level**: low / medium / high / critical
- **Regulatory triggers**: patient data → CMIO activates. Export control → Petra activates. OT boundary → Erik activates. Personal data → Aisha + Nadia activate.

**How personas drive this step:**

Classification determines **who's in the room**. `selectRelevant()` maps request type to persona subset:

```javascript
'clinical-system': ['cio', 'cmio', 'chief', 'application', 'integration', 'data', 'security', 'risk']
'infrastructure-change': ['chief', 'infrastructure', 'security', 'risk']
'vendor-selection': ['cio', 'chief', 'application', 'integration', 'security', 'risk']
```

Governance baseline — Chief Architect, Security, and Risk are **always** in the room.

Red Team activates only for high/critical impact: `selectRelevant(PERSONAS, type, { includeRedTeam: impact >= 'high' })`.

### Step 2 — Retrieve (Persona-Scoped Knowledge)

Based on classification and selected personas, pull relevant context.

**How personas drive this step:**

Each selected persona's `domain` field becomes a RAG query scope. Retrieval is **per-persona**, not global:

| Selected Persona | Retrieves from Milvus |
|------------------|----------------------|
| Victor (Security) | Security policies, zero-trust standards, threat modeling templates, SBOM requirements |
| Nadia (Risk) | Regulatory applicability matrices, risk appetite definitions, third-party assessment checklists |
| Thomas (Application) | Tech radar, application lifecycle policies, SaaS evaluation criteria, vendor viability thresholds |
| Lena (Integration) | API standards, event-driven architecture patterns, integration SLAs, coupling risk frameworks |
| CMIO | Clinical system policies, FHIR compliance requirements, MDR/IVDR software classification rules |
| Aisha (Data) | Data classification scheme, GDPR processing rules, DPIA templates, EU AI Act risk tiers |

Each persona gets **its own context bundle** — not the entire knowledge base. Victor doesn't need PLM integration standards. Petra doesn't need FHIR compliance rules.

Also refines what to look for in the ArchiMate model and TOPdesk based on classification (targeted queries that Step 0 didn't know to make yet).

### Step 3 — Assess (Persona Evaluation)

Two modes, matching OpenClaw's MiroFish patterns:

#### Fast Mode — Batched PERSPECTIVES (single LLM call)

For standard intake triage. Uses condensed `PERSPECTIVES` array — all selected perspectives in one prompt, one response:

```
## Perspectives
- **cio** (CIO — Strategy & Investment): IT strategy, budget justification, TCO...
- **chief** (Chief Architect — Coherence): target architecture fit, capability map...
- **security** (Security Architecture — VETO): STRIDE, zero trust, IAM design...
- ...

## Proposal
[business request + landscape brief + vendor docs]

## Retrieved Context
[per-persona knowledge bundles from Step 2]

## Task
Rate this proposal from EACH perspective.
Use: approve, conditional, concern, block, na

Output format:
[1] cio:conditional chief:approve security:concern risk:conditional ...

For each non-approve rating, add one line:
cio: [reason in one sentence]
security: [reason in one sentence]
```

Parsed by `parseAssessmentRatings()`. Aggregated by `determineTriageLevel()`.

#### Deep Mode — simulatePanel() (per-persona LLM calls)

For high-impact proposals. Uses full `PERSONAS` array with OpenClaw's `simulatePanel()`:

```javascript
const result = await simulatePanel(
  selectedPersonas,  // 5-9 personas with landscape context in history
  {
    description: 'Digital Pathology from Sysmex — whole slide imaging...',
    decision: 'Acquire and integrate into clinical workflow',
    context: vendorDocs + landscapeBrief + retrievedKnowledge,
  },
  { interactionRounds: 1, requireDissent: true }
);
```

Each persona gets its own LLM call. Responds in character with:
1. **Initial reaction** — how they feel about this
2. **Strongest objection** — what could kill it from their perspective
3. **Hidden concern** — what they're thinking but won't say in the meeting
4. **Conditions for approval** — what they need to say yes

Optional interaction round: personas see each other's reactions and respond. Do they change position? Who do they ally with?

Then synthesis: predicted outcome, coalition map, top 3 risks, recommended actions.

**Mode selection:**

| Impact | Mode | Why |
|--------|------|-----|
| Low | Fast (batched) | Quick triage, single call |
| Medium | Fast (batched) | Standard review, efficient |
| High | Deep (panel) | Full stakeholder simulation, interaction rounds |
| Critical | Deep (panel) + 2 interaction rounds | Maximum scrutiny |

### Step 4 — Challenge (Authority Personas Act)

Not just "adversarial review." This is where personas with **special authority** exercise it.

**How personas drive this step:**

Three things happen, in order:

**4a. Security Veto Check (Victor)**

If Victor's assessment is `block` (fast mode) or his strongest objection is severity:critical (deep mode):
- Pipeline flags: `SECURITY VETO — proposal cannot proceed in current form`
- Victor's conditions for approval become **mandatory requirements**, not suggestions
- Output is shaped as a rejection with remediation path

**4b. Risk Escalation Check (Nadia)**

If Nadia's assessment is `block` or risk exceeds defined appetite:
- Pipeline flags: `RISK ESCALATION — requires senior management decision`
- Nadia's regulatory findings become the first section of the output
- Board treatment automatically upgrades to deep-review

**4c. FG/DPO Lawfulness Determination (FG-DPO)**

If the FG determines the proposed data processing is unlawful (no valid verwerkingsgrondslag, disproportionate, missing DPIA where required):
- Pipeline flags: `FG DETERMINATION — processing is unlawful in current form`
- This is NOT a veto that can be escalated or overridden. It is a legal determination under AVG Article 38(3).
- The only path forward: change the proposal until the FG determines it is lawful.
- Output includes the FG's specific findings and what must change.

**4d. Red Team Pre-Mortem (Raven)**

Triggers when:
- Impact is high/critical, AND
- Steps 4a/4b did not already block

Raven receives all other persona assessments and runs adversarial review — not on the proposal, but **on the assessments themselves**:
- What did the other personas miss?
- Where did they agree too easily? (groupthink detection)
- What assumptions are they all sharing that might be wrong?
- Pre-mortem: it's 12 months later, this failed. The failure mode was something **none** of the domain personas flagged. What was it?

This is meta — the Red Team challenges the assessment, not just the proposal.

### Step 5 — Output (Architecture Products)

Every finding is **attributed to the persona that raised it**. The board doesn't read anonymous concerns — they read named positions from known roles.

Preflight generates **draft architecture products** — the documents architects actually spend their time creating. Not final versions. Drafts grounded in landscape data, persona assessments, and ZiRA, ready for the architect to refine and own.

#### Language: Dutch + English

All products, the interface, and persona output are bilingual:

- **Dutch (NL):** Default for internal hospital use. ZiRA terminology is Dutch-native — bedrijfsfuncties, informatiedomeinen, procesmodel. Board members read Dutch.
- **English (EN):** For international vendor communication, English-speaking stakeholders, and export.

Language is set per assessment. Personas respond in the selected language. Templates exist in both languages. The architect can switch output language without re-running the assessment.

#### Triage Logic

`determineTriageLevel()` aggregates persona ratings into board treatment:

| Condition | Treatment |
|-----------|-----------|
| FG determines unlawful | **Rejected** — cannot proceed until lawful (not overridable) |
| Victor blocks | Deep review (veto) |
| Nadia blocks | Deep review (escalation) |
| Any persona blocks | Deep review |
| 2+ personas have concerns | Standard review |
| All approve/conditional, ≤2 conditionals | Fast-track |
| Clear policy violation detected | Reject early |

#### Architecture Products

Preflight generates these products based on assessment results and triage level:

| Product | NL Name | When Generated | Primary Personas | Content |
|---------|---------|----------------|------------------|---------|
| **Project Start Architecture** | Project Start Architectuur (PSA) | Every assessment (the main output) | All selected | Full multi-domain assessment, ZiRA mapping, principles check, landscape impact, conditions, risk register |
| **Architecture Decision Record** | Architectuurbesluit (ADR) | Every decision point | Marcus + relevant domain | Decision, context, options considered, chosen option, rationale, consequences |
| **Vendor/Product Assessment** | Leveranciers-/Productbeoordeling | When proposal involves new vendor/product | CIO, Thomas, Lena, Victor, Nadia | Vendor scorecard, tech radar position, integration complexity, security posture, compliance status, TCO |
| **Data Protection Impact Assessment** | Gegevensbeschermingseffectbeoordeling (DPIA) | When personal/patient data is involved | Aisha, Victor, Nadia, CMIO | Data flows with classification, processing grounds, risks, mitigations, GDPR articles, processor agreements |
| **Business Impact Analysis + BIV** | Bedrijfsimpactanalyse (BIA) + BIV-classificatie | When business-critical systems are affected | Jan, Victor, Nadia, CIO, CMIO | BIV classification, impact per ZiRA process, RPO/RTO, dependencies, cascade analysis, continuity measures (see BIA/BIV design below) |
| **Integration Design** | Integratieontwerp | When systems need to connect | Lena, CMIO (for clinical), Jan | Integration pattern, API/HL7v2/FHIR specification, data flow diagram, Cloverleaf routing, error handling |
| **Security Assessment** | Beveiligingsbeoordeling | Every assessment (embedded in PSA, standalone for high-impact) | Victor | STRIDE threat model, attack surface, zero-trust mapping, SBOM requirements, pen test scope |
| **Tech Radar Update** | Technologieradar Update | When new technology enters the landscape | Thomas | Technology name, category, ring (ADOPT/TRIAL/ASSESS/HOLD), rationale, conditions for movement |

#### Product Selection Logic

Not every assessment generates every product. The pipeline selects based on what the assessment triggers:

```
Every assessment → PSA (always) + ADR (always)

If new vendor/product    → + Vendor Assessment
If personal/patient data → + DPIA
If business-critical     → + BIA
If system integration    → + Integration Design
If high security impact  → + standalone Security Assessment
If new technology        → + Tech Radar Update
```

The architect can also request specific products manually: "Run Preflight on this proposal, I need a DPIA and Integration Design."

#### BIA + BIV Design

The BIA is where Preflight's value becomes tangible for the board — it translates technical architecture into business risk language. In a hospital, "system X goes down" isn't an IT problem, it's a patient safety question.

**BIV Classification (Beschikbaarheid, Integriteit, Vertrouwelijkheid)**

Every system/proposal gets a BIV classification — the Dutch standard for the CIA triad. Each dimension is scored independently because a system can be highly confidential but tolerate some downtime, or vice versa.

| Dimensie | NL | EN | Question | Scored by |
|----------|----|----|----------|-----------|
| **B** | Beschikbaarheid | Availability | How long can this system be unavailable before patient care, operations, or compliance is impacted? | Jan (Infrastructure), CMIO (clinical) |
| **I** | Integriteit | Integrity | What is the impact if data in this system is incorrectly modified, corrupted, or incomplete? | Aisha (Data), CMIO (clinical), Victor (Security) |
| **V** | Vertrouwelijkheid | Confidentiality | What is the impact if data in this system is accessed by unauthorized persons? | Victor (Security), Nadia (Compliance), CMIO (if patient data) |

**BIV scoring scale:**

| Score | Level | B — Beschikbaarheid | I — Integriteit | V — Vertrouwelijkheid |
|-------|-------|---------------------|-----------------|----------------------|
| **3** | Hoog / High | Uitval >1 uur: direct risico voor patiëntveiligheid of wettelijke verplichting. Zorgproces kan niet handmatig worden voortgezet. | Onjuiste data leidt direct tot verkeerde klinische beslissingen of foutieve rapportage aan toezichthouder. | Ongeautoriseerde toegang leidt tot schending medisch beroepsgeheim, AVG-melding aan AP verplicht, persoonlijk letsel betrokkenen. |
| **2** | Midden / Medium | Uitval >4 uur: significante hinder voor bedrijfsvoering, workaround beschikbaar maar kostbaar. | Onjuiste data leidt tot vertraging of herwerk, geen direct patiëntrisico. | Ongeautoriseerde toegang leidt tot reputatieschade, mogelijke AVG-melding, geen direct persoonlijk letsel. |
| **1** | Laag / Low | Uitval >24 uur: beperkte impact, handmatige alternatieven beschikbaar. | Onjuiste data heeft beperkte impact, eenvoudig te herstellen. | Ongeautoriseerde toegang heeft beperkte impact, geen persoonsgegevens betrokken. |

**How personas score BIV:**

Each relevant persona independently assesses their dimension. The pipeline takes the **highest score per dimension** (conservative — one persona flagging high overrides others flagging medium):

```
B (Beschikbaarheid):
  Jan scores:  2 (workaround available via failover)
  CMIO scores: 3 (lab results unavailable → clinical decisions delayed)
  → Final B = 3 (CMIO's clinical perspective overrides)

I (Integriteit):
  Aisha scores: 2 (data quality issue, no direct clinical impact)
  CMIO scores:  3 (incorrect lab values → wrong diagnosis)
  Victor scores: 2 (integrity controls in place)
  → Final I = 3 (CMIO's patient safety perspective overrides)

V (Vertrouwelijkheid):
  Victor scores: 3 (patient data, medical records)
  Nadia scores:  3 (bijzondere persoonsgegevens under AVG)
  CMIO scores:   3 (medisch beroepsgeheim under WGBO)
  → Final V = 3 (unanimous)
```

**BIV feeds into other systems:**

| BIV Score | Triggers |
|-----------|----------|
| B=3 | RPO ≤ 1 hour, RTO ≤ 1 hour, DR plan mandatory, ISO 22301 scope |
| B=2 | RPO ≤ 4 hours, RTO ≤ 4 hours, DR plan required |
| I=3 | Data validation controls mandatory, audit trail on all mutations, backup verification |
| I=2 | Standard data quality controls, periodic integrity checks |
| V=3 | NEN 7510 full scope, encryption at rest + transit, NEN 7513 logging, ABAC patient-data policy, DPIA required |
| V=2 | Standard access control, encryption in transit, standard logging |
| Any dimension = 3 | BIA automatically upgrades to full report, board treatment = deep review |

**BIA Impact Dimensions (hospital-specific):**

| Dimension | Question | Input Source | Scored by |
|-----------|----------|-------------|-----------|
| Patiëntveiligheid | Could unavailability, data corruption, or data breach directly harm patients? | CMIO clinical assessment | CMIO |
| Zorgcontinuïteit | Which of the 8 ZiRA zorgprocessen are affected? Can they continue handmatig? For how long? | ArchiMate model (process → application mapping), ZiRA procesmodel | CMIO, Sophie |
| Cascade-risico | What other systems fail when this one fails? What's the blast radius? | ArchiMate model (serving/flow relationships), TOPdesk CMDB (CI dependencies) | Lena, Jan |
| Regelgeving | Does downtime trigger reporting obligations? (NIS2 24h to CSIRT, IGJ melding, AP melding) | Nadia's regulatory assessment | Nadia |
| Financiële impact | Revenue loss, penalties, recovery cost, overtime — per hour of downtime | CIO assessment + TOPdesk (historical incident cost if available) | CIO |
| Reputatie | Public-facing system? Media risk? Patient communication affected? | CIO assessment | CIO |
| Data-integriteit | Could data be lost or corrupted? What's the recovery path? Backup RPO achievable? | Jan infrastructure assessment + Aisha data assessment | Aisha, Jan |

**BIA output template:**

```markdown
# Bedrijfsimpactanalyse: [Systeemnaam / Voorstel]
# Business Impact Analysis: [System name / Proposal]

## BIV-classificatie / CIA Classification
| Dimensie | Score | Toelichting | Beoordelaar |
|----------|-------|-------------|-------------|
| B — Beschikbaarheid | 3 (Hoog) | Lab results unavailable → clinical decisions delayed | CMIO |
| I — Integriteit | 3 (Hoog) | Incorrect lab values → wrong diagnosis possible | CMIO |
| V — Vertrouwelijkheid | 3 (Hoog) | Patient data, medisch beroepsgeheim | Victor, Nadia, CMIO |

## RPO/RTO Doelen / Recovery Targets
| Metric | Doel | Verantwoording |
|--------|------|----------------|
| RPO (Recovery Point Objective) | ≤ 1 uur | B=3: patiëntveiligheid |
| RTO (Recovery Time Objective) | ≤ 1 uur | B=3: patiëntveiligheid |
| MTPD (Maximum Tolerable Period of Disruption) | 2 uur | Klinisch proces stopt volledig na 2 uur |

## Getroffen ZiRA Zorgprocessen
| Proces | Impact | Handmatig voort te zetten? | Maximale duur handmatig |
|--------|--------|---------------------------|------------------------|
| Diagnosticeren | Hoog | Beperkt (papieren aanvragen) | 4 uur |
| Behandelen | Midden | Ja (mondelinge overdracht) | 8 uur |
| Aanvullend onderzoek | Hoog | Nee (apparatuur afhankelijk) | 0 uur |

## Cascade-analyse / Dependency Analysis
[ArchiMate-based: which systems depend on this, what breaks downstream]
| Afhankelijk systeem | Relatie | Impact bij uitval |
|---------------------|---------|-------------------|
| EPD | Serving | Geen lab resultaten beschikbaar |
| PACS (JiveX) | Flow | Beeldvorming niet koppelbaar aan order |

## Meldplichten / Reporting Obligations
| Verplichting | Termijn | Trigger |
|-------------|---------|---------|
| NIS2 → CSIRT | 24 uur (early warning), 72 uur (incident notification) | B=3 systeem, uitval >1 uur |
| IGJ melding | Onverwijld | Patiëntveiligheid in het geding |
| AP melding | 72 uur | Als datalek bij V=3 systeem |

## Continuïteitsmaatregelen / Continuity Measures
[Jan's infrastructure assessment: what's in place, what's needed]

## Financiële Impact / Financial Impact
[CIO's assessment: cost per hour of downtime]

## Aanbevelingen / Recommendations
[Consolidated from all persona assessments]
```

The BIV classification cascades through the entire Preflight assessment — it influences the ABAC access policies (V=3 → restrict access), the audit trail requirements (V=3 → NEN 7513 full logging), the board treatment (any 3 → deep review), and the conditions for approval (B=3 → DR plan mandatory before go-live).

#### PSA Template Structure (primary output)

The PSA is the main product — it's the gateway document in Dutch hospital EA practice.

```markdown
# Project Start Architectuur: [Naam voorstel]
# Project Start Architecture: [Proposal name]

## 1. Managementsamenvatting / Management Summary
Triage: [FAST-TRACK / STANDAARD REVIEW / DIEPGAANDE REVIEW / VROEGTIJDIG AFWIJZEN]
[One paragraph: what, why, recommendation]

## 2. Context en Aanleiding / Context and Motivation
[Business request, landscape context from Step 0]

## 3. ZiRA Positionering / ZiRA Positioning
- Bedrijfsdomein(en): [Zorg / Onderzoek / Onderwijs / Sturing / Bedrijfsondersteuning]
- Bedrijfsfuncties: [mapped from bedrijfsfunctiemodel]
- Diensten: [mapped from dienstenmodel]
- Processen: [which of the 8 primary care processes]
- Informatiedomeinen: [mapped from informatiedomeinenmodel]
- Applicatiefuncties: [mapped from applicatiefunctiemodel]

## 4. Principetoets / Principles Assessment
| ZiRA Principe | Beoordeling | Toelichting |
|---------------|-------------|-------------|
| Waardevol | ✓ / △ / ✗ | [rationale] |
| Veilig en vertrouwd | ✓ / △ / ✗ | [rationale] |
| ... | | |

## 5. Domeinbeoordelingen / Domain Assessments
### CIO (Strategie & Investering): [AKKOORD / VOORWAARDELIJK / BEZORGD / BLOKKADE]
[Finding + conditions — attributed to persona]

### Victor (Beveiligingsarchitectuur): [AKKOORD / VOORWAARDELIJK / BEZORGD / BLOKKADE]
[STRIDE findings + conditions]

### Nadia (Risico & Compliance): [AKKOORD / VOORWAARDELIJK / BEZORGD / BLOKKADE]
[Regulatory assessment]

[...all selected personas...]

## 6. Risicoregister / Risk Register
| Risico | Gesignaleerd door | Ernst | Mitigatie |
|--------|-------------------|-------|-----------|
| Geen STRIDE dreigingsmodel | Victor | Hoog | Afronden voor boardbespreking |
| Overlap met bestaande Lab360 | Thomas | Midden | Uitfaseringsplan opstellen |
| Patiëntgegevens — DPIA vereist | Aisha | Hoog | DPIA-proces starten |

## 7. Red Team Bevindingen / Red Team Findings (indien van toepassing)
[Raven's adversarial review]

## 8. Voorwaarden voor Goedkeuring / Conditions for Approval
[Consolidated from all personas — deduplicated, prioritized]

## 9. Open Vragen voor de Board / Open Questions for the Board
[Things Preflight can't answer — political, budgetary, strategic]

## 10. Bijlagen / Appendices
[Links to generated DPIA, BIA, Integration Design, Vendor Assessment if applicable]
```

Every section traces back to a persona. The board knows exactly which role flagged what.

## Knowledge Base

### Reference Architecture: ZiRA

Preflight is grounded in the **ZiRA (Ziekenhuis Referentie Architectuur)** — the Dutch hospital reference architecture maintained by Nictiz. Every assessment maps to ZiRA's models:

| ZiRA Model | Used by | Purpose in Preflight |
|------------|---------|---------------------|
| **12 Architectuurprincipes** | Marcus (Chief) | Every proposal evaluated against principles (Waardevol, Veilig, Duurzaam, Flexibel, Eenvoudig, etc.) |
| **Bedrijfsfunctiemodel** | Marcus, Sophie | Map proposal to business functions across 5 domains (Zorg, Onderzoek, Onderwijs, Sturing, Bedrijfsondersteuning) |
| **Dienstenmodel** | Sophie | Which diensten are impacted (diagnostiek, advies, behandeling, etc.) |
| **Procesmodel** | Sophie, CMIO | Which of the 8 primary care processes are affected |
| **Informatiemodel + zibs** | Aisha | Information objects, zorginformatiebouwstenen, data classification |
| **Informatiedomeinenmodel** | Marcus, Aisha | Domain boundaries for information governance |
| **Applicatiefunctiemodel** | Thomas | Map to vendor-independent application functions per domain |
| **Metamodel** | Marcus | Validate chain: diensten → bedrijfsprocessen → werkprocessen → bedrijfsfuncties |

ZiRA v1.4 is current. The transition to **ZaRA** (Zorgaanbieder Referentie Architectuur) — which merges ZiRA + RDC + RDGGZ into one care-wide architecture — is tracked. Marcus evaluates whether proposals align with ZaRA direction where applicable.

The ZiRA `.archimate` model file is loaded into Preflight's ArchiMate parser alongside the hospital's own Archi model. This means Preflight can cross-reference "what ZiRA says should exist" with "what actually exists in our landscape."

### Knowledge Corpus

The knowledge corpus lives as markdown files, chunked and embedded into Milvus:

```
knowledge/
├── zira/                     # ZiRA reference architecture (extracted from .archimate + .xlsx)
│   ├── principes/            # 12 architecture principles with rationale and implications
│   ├── bedrijfsfuncties/     # Business functions by domain
│   ├── diensten/             # Services model
│   ├── processen/            # 8 primary care processes
│   ├── informatiemodel/      # Information objects + zibs mapping
│   └── applicatiefuncties/   # Application functions by domain
├── regulatory/                   # Regulatory & standards compliance
│   ├── avg/                      # AVG/GDPR — verwerkingsgrondslagen, rechten betrokkenen, DPIA criteria, meldplicht
│   ├── nen/                      # NEN healthcare standards
│   │   ├── nen-7510.md           # Informatiebeveiliging in de zorg (ISMS, controls, gap analysis checklist)
│   │   ├── nen-7512.md           # Vertrouwensbasis gegevensuitwisseling (trust levels, authentication requirements)
│   │   ├── nen-7513.md           # Logging toegang patiëntgegevens (logging requirements, retention, audit)
│   │   ├── nen-7516.md           # Veilige e-mail in de zorg
│   │   └── nen-7517.md           # Toestemming elektronische gegevensuitwisseling
│   ├── iso/                      # ISO standards (applicability matrices, control mappings)
│   │   ├── iso-27001.md          # ISMS requirements
│   │   ├── iso-27701.md          # Privacy information management
│   │   ├── iso-13485.md          # Medical devices QMS
│   │   ├── iec-62304.md          # Medical device software lifecycle
│   │   └── iec-80001.md          # IT-networks with medical devices
│   └── sector/                   # Sector-specific regulation
│       ├── nis2.md               # Netwerk- en informatiebeveiliging
│       ├── mdr-ivdr.md           # Medical device / IVD regulation
│       ├── wegiz.md              # Wet elektronische gegevensuitwisseling in de zorg
│       └── eu-ai-act.md          # AI risk classification for healthcare
├── procurement/                  # Procurement compliance
│   ├── aivg-2022.md              # Algemene Inkoopvoorwaarden Gezondheidszorg 2022
│   └── aivg-module-ict.md        # AIVG 2022 Module ICT (informatiebeveiliging, IP, escrow, exit, SaaS, hosting)
├── hospital/                 # Hospital-specific knowledge
│   ├── principles/           # Local architecture principles (extending ZiRA)
│   ├── policies/             # Mandatory and standard policies by domain
│   ├── standards/            # Technology standards, naming, documentation
│   ├── tech-radar/           # ADOPT / TRIAL / ASSESS / HOLD
│   └── reference-architectures/  # Approved patterns
└── glossary/                 # Terminology (aligned with ZiRA begrippenlijst)
```

Retrieval is persona-scoped: each persona's `domain` keywords drive which chunks are retrieved for their evaluation context. Not a global dump.

Maintenance is manual but lightweight — update a markdown file, re-embed. Build a simple CI job that re-indexes on merge to main.

## What Preflight Explicitly Leaves to Humans

- Final decision authority
- Political and organizational context
- Budget trade-offs and funding decisions
- Vendor relationship considerations
- Strategic bets ("we know this is risky but we're doing it anyway")
- Accountability for outcomes
- Overriding Preflight's recommendation with documented rationale

These are surfaced in every Preflight output under **"Open Questions for the Board"** so the board knows exactly what still needs human judgment.

## Dogfooding: Personas Govern Preflight's Development

The same 17 personas that evaluate business requests at runtime also evaluate every architecture and design decision made building Preflight itself. Same `selectRelevant()`, same incentives, same constraints. If Victor would block a customer's proposal for missing a threat model, he blocks your PR for the same reason. If the FG says Preflight's own data processing is unlawful, it doesn't ship.

### How It Works

Every significant development decision is a proposal. Run it through the personas before building it.

| Development Decision | Relevant Personas | What They Check |
|---------------------|-------------------|-----------------|
| "Add Milvus for RAG" | Thomas, Jan, Victor, Nadia | Portfolio impact, infrastructure cost, security posture, license compliance |
| "Store vendor docs in blob storage" | Victor, Aisha, Nadia | Data classification, encryption at rest, access control, retention policy |
| "Build ArchiMate model parser" | Thomas, Lena, Marcus | Model coverage, element type handling, relationship traversal |
| "Deploy Nemotron NIM on GPU cluster" | Jan, Victor, CIO | Infrastructure cost, DR plan, security hardening, budget justification |
| "Add Teams Adaptive Card output" | Lena, Victor | Integration pattern, data leakage risk (what goes in the card vs. stays internal) |
| "Use FastAPI for the service layer" | Thomas, Jan, Victor | Tech radar position, dependency supply chain, operational readiness |
| "Handle patient data in proposals" | CMIO, Aisha, Victor, Nadia | Clinical data classification, GDPR/HIPAA, encryption, DPIA, access audit trail |

### Development Modes

Same two modes as runtime:

**Fast mode (most decisions):** Quick batched check — "would any persona block this?" Run the PERSPECTIVES against the decision in a single call. If all approve/conditional, proceed.

**Deep mode (architecture decisions):** Full `simulatePanel()` — when you're choosing the vector database, designing the data model, or defining the deployment architecture. These are the decisions that are expensive to reverse. Get the full panel reaction, interaction round, synthesis.

### What This Catches

Things you'd miss without the personas reviewing your own work:

- **Victor** catches that you're storing API keys in environment variables without a secrets manager
- **Aisha** catches that vendor documents uploaded to Preflight may contain personal data you haven't classified
- **Nadia** catches that your NIM deployment in Azure needs a DPIA because proposal data may contain patient information
- **Thomas** catches that you're adding Milvus when the organization already has a Weaviate instance
- **Lena** catches that your ArchiMate parser only traverses one level of relationships when integration impact needs the full dependency chain
- **Jan** catches that your deployment has no DR plan — "what happens when the GPU node fails mid-assessment?"
- **Raven** catches that everyone assumed Nemotron would be good enough for structured EA assessment without benchmarking it first

### The Rule

**No architecture decision ships without a Preflight assessment of that decision.** The output lives in the PR description or a linked ADR. The board treatment applies: fast-track for low-impact changes, full review for infrastructure and security decisions.

This is not overhead. This is the tool proving it works by using itself.

## Build Phases

Each phase gets a Preflight assessment before starting. The personas evaluate the phase scope, technology choices, and risk profile — the same way they'd evaluate any business request.

### Phase 1 — Core (weeks 1-2)

**Preflight assessment of Phase 1:** Run the phase plan through fast-mode personas. Key questions: Does the FastAPI choice fit the tech radar? Is the NIM deployment architecture sound? What's the minimum viable security posture for a tool that will ingest vendor documents?

Build:
- FastAPI service with request intake endpoint
- Nemotron NIM deployment
- Load personas from `ea-council-personas.mjs`
- Step 1: classification + `selectRelevant()` routing
- Step 3 fast mode: batched PERSPECTIVES single-call assessment
- Step 5: Markdown output with persona-attributed findings
- Manual knowledge base (embedded once, no CI yet)

### Phase 2 — Grounded (weeks 3-4)

**Preflight assessment of Phase 2:** Deep-mode panel on ArchiMate and TOPdesk integration design. Victor reviews auth and secret handling. Lena reviews API patterns. Nadia reviews data processing implications of querying enterprise systems.

Build:
- ArchiMate model parser (persona-driven landscape queries in Step 0)
- TOPdesk REST integration (persona-driven queries in Step 0)
- `injectLandscapeContext()` pipeline
- RAG pipeline with Milvus (persona-scoped retrieval in Step 2)
- Triage-based output formats (fast-track / standard / deep)
- `determineTriageLevel()` with veto/escalation logic

### Phase 3 — Deep (weeks 5-6)

**Preflight assessment of Phase 3:** The simulatePanel() integration means Preflight now makes multiple sequential LLM calls per assessment. Jan reviews compute cost and scaling. CIO reviews whether the deep mode cost is justified by the value. Raven stress-tests: what if interaction rounds produce garbage?

Build:
- Step 3 deep mode: `simulatePanel()` integration for high-impact proposals
- Interaction rounds (personas react to each other's positions)
- Step 4: Security veto + Risk escalation + Red Team pre-mortem chain
- NeMo Guardrails integration
- Knowledge base CI (re-index on merge)
- Teams Adaptive Card output format

### Phase 4 — Learn (ongoing)

**Preflight assessment of Phase 4:** Aisha reviews the feedback data model — what are we storing about board members' assessments? Nadia checks if tracking per-persona accuracy creates governance issues. Victor reviews whether feedback data could be used to game the system.

Build:
- Feedback capture: board can mark each persona's finding as "useful / missed the point / wrong"
- Per-persona accuracy tracking — which personas consistently add value vs. noise?
- Tune persona incentives/constraints based on where they consistently miss
- Track hit rate: how often does the board agree with Preflight's triage?
- Track veto accuracy: when Victor blocks, does the board agree?
- Expand knowledge base based on recurring gaps

## Success Metrics

| Metric | Target |
|--------|--------|
| Time from business request to first structured assessment | < 5 minutes (vs. days/weeks today) |
| Board prep time per proposal | Reduced by 60%+ |
| Requests resolved without full board session | 40%+ (via fast-track and early reject) |
| Persona coverage per review | 100% of relevant domain lenses consulted |
| Board agreement with Preflight triage | >80% |
| Board agreement with Preflight recommendation | >70% |
| Veto accuracy (board agrees with Victor's blocks) | >90% |
| Per-persona usefulness (board marks findings as useful) | >70% per persona |
| Adoption | Architects voluntarily use it (not mandated) |

## Estimated Footprint

- ~800-1000 lines of Python for orchestration
- LLM via NIM (self-hosted) or Ollama (local dev) — model choice deferred
- 1 Milvus instance
- 4 integrations (ArchiMate model parser, TOPdesk REST, SharePoint + OneDrive via Microsoft Graph)
- 17 MiroFish personas (permanent, reusable across all assessments)
- Marginal cost per assessment: near zero for light/strong tiers; frontier tier cost-per-call for high-impact only

## Repository

Source: https://github.com/rvdlaar/preflight

```
preflight/
├── PREFLIGHT.md                       # This document
├── personas/
│   ├── ea_council.py                  # 17 MiroFish personas (ported from .mjs)
│   ├── routing.py                     # selectRelevant() + ROUTING table
│   └── enrichment.py                  # injectLandscapeContext()
├── knowledge/                         # RAG corpus (markdown → Milvus)
│   ├── principles/
│   ├── policies/
│   ├── standards/
│   ├── tech-radar/
│   ├── reference-architectures/
│   └── glossary/
├── src/
│   ├── server.py                      # FastAPI service
│   ├── pipeline.py                    # Six-step orchestration
│   ├── ingest.py                      # Step 0 — persona-driven discovery
│   ├── classify.py                    # Step 1 — classification + routing
│   ├── retrieve.py                    # Step 2 — persona-scoped RAG
│   ├── assess.py                      # Step 3 — fast/deep mode assessment
│   ├── simulate.py                    # simulatePanel() — ported from OpenClaw
│   ├── challenge.py                   # Step 4 — veto/escalation/red team
│   ├── output.py                      # Step 5 — product generation + language selection
│   ├── products/                      # Architecture product generators
│   │   ├── psa.py                     # Project Start Architectuur
│   │   ├── adr.py                     # Architecture Decision Record
│   │   ├── vendor.py                  # Vendor/Product Assessment
│   │   ├── dpia.py                    # Data Protection Impact Assessment
│   │   ├── bia.py                     # Business Impact Analysis
│   │   ├── integration.py             # Integration Design
│   │   ├── security.py                # Security Assessment / Threat Model
│   │   └── techradar.py               # Tech Radar Update
│   ├── templates/                     # Bilingual product templates
│   │   ├── nl/                        # Dutch templates
│   │   └── en/                        # English templates
│   ├── i18n.py                        # Language switching (NL/EN)
│   ├── auth/
│   │   ├── authn.py                  # Microsoft Entra ID (OIDC) — identity
│   │   ├── authz.py                  # OAuth 2.1 + RBAC/ABAC policy engine
│   │   └── policies.py              # ABAC policies (patient data, export control, vendor-confidential)
│   ├── audit/
│   │   ├── trail.py                  # Append-only hash-chained audit log (PostgreSQL)
│   │   ├── siem.py                   # SIEM export (CEF/syslog)
│   │   └── compliance.py             # NEN 7513 / NIS2 / MDR / SOC 2 report generators
│   ├── parsing/
│   │   ├── router.py                 # File type detection + parser routing
│   │   ├── markitdown.py             # DOCX/PPTX/XLSX → Markdown (local)
│   │   ├── pymupdf.py                # Digital PDFs → Markdown (local)
│   │   ├── llamaparse.py             # Complex PDFs → Markdown (cloud/self-hosted)
│   │   ├── azure_doc.py              # Scanned/OCR → Markdown (Azure tenant)
│   │   └── unstructured.py           # Mixed docs + chunking (self-hosted)
│   ├── embedding/
│   │   ├── pipeline.py               # Orchestrates chunking → embedding → Milvus
│   │   ├── chunkers/
│   │   │   ├── archimate.py          # Object-based (element + relationships)
│   │   │   ├── hierarchical.py       # Parent-child (vendor docs)
│   │   │   ├── contextual.py         # LLM-prefixed (ZiRA/AIVG/NEN specs)
│   │   │   └── tabular.py            # Row-wise Markdown (Excel/tables)
│   │   └── models/
│   │       ├── voyage.py             # Voyage-3-Large client
│   │       ├── bge.py                # BGE-M3 multilingual client
│   │       └── gemini.py             # Gemini 2.0 for table embeddings
│   ├── integrations/
│   │   ├── archimate.py              # Archi .archimate XML parser
│   │   ├── topdesk.py                # TOPdesk REST — CMDB, change, GRC
│   │   └── msgraph.py                # Microsoft Graph — SharePoint + OneDrive
│   └── llm/
│       ├── router.py                  # LLMRouter — light/strong/frontier dispatch
│       ├── nim.py                     # NVIDIA NIM client
│       └── ollama.py                  # Ollama client (local dev)
├── frontend/                          # Next.js + shadcn/ui + Tailwind
│   ├── design-system/                 # Generated by UI UX Pro Max
│   └── src/
│       ├── app/                       # Next.js app router
│       │   ├── [locale]/              # NL/EN bilingual routes
│       │   ├── assessments/           # Assessment list, detail, history
│       │   ├── intake/                # New request intake form
│       │   └── dashboard/             # Overview, metrics, recent assessments
│       └── components/                # Shared UI components
├── tests/
│   └── scenarios/                     # Test proposals (Digital Pathology, etc.)
└── assessments/                       # Dogfood: Preflight assessments of Preflight
    └── phase-1-tech-stack.md          # First self-assessment
```

---

*Preflight does the homework. The architect adds judgment. The board makes the call.*
