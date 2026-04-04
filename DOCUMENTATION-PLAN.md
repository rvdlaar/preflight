# Documentation Plan — Preflight

The panel said: PREFLIGHT.md tries to be both a product brief and a technical architecture document.
It's too long for the first and too shallow for the second. Split it.

---

## New Document Structure

```
EA-Council/
├── PREFLIGHT.md              ← REWRITTEN: Product document (what it does, for whom, why)
├── ARCHITECTURE.md            ← NEW: Technical architecture (how it works under the hood)
├── DIGITAL-PATHOLOGY.md       ← NEW: Worked example end-to-end
├── personas/
│   └── ea-council-personas.mjs  ← EXISTS: persona definitions (update per 4.4)
├── templates/                 ← NEW: Output product templates
│   ├── psa.md                 ← Full PSA template with field descriptions
│   ├── bia-biv.md             ← BIA + BIV template
│   ├── integration-design.md  ← NEW: Integration design template (Lena's gap)
│   ├── vendor-assessment.md   ← Vendor/product assessment template
│   ├── dpia.md                ← DPIA template
│   ├── adr.md                 ← ADR template (Marcus's gap — which format? MADR?)
│   ├── security-assessment.md ← STRIDE-based security assessment
│   ├── tech-radar-update.md   ← Tech radar entry template
│   └── clinical-impact.md     ← NEW: CMIO's 1-page clinical brief
└── PROMPTS-v2.md              ← Prompt backlog for executing improvements
```

---

## PREFLIGHT.md — Rewritten Structure

This is the product document. The CIO reads this. The CMIO reads this. A new architect at a conference reads this and thinks "I need this."

```markdown
# Preflight

"Run it through Preflight."

## The Problem                                         ← KEEP (panel loved this)
  [Current: weeks to months, structured work not judgment]

## What You Get                                        ← NEW (replaces "What It Is")
  Walk through what each role experiences:
  
  ### If you're an architect
  - Paste a business request. Get a draft PSA in minutes.
  - Landscape context auto-queried from your Archi model.
  - ZiRA positioning pre-filled: bedrijfsdomein, functies, diensten, processen.
  - 12 domain perspectives assessed. Risk register populated.
  - You refine for an hour. Present a PSA that would have taken a week.
  
  ### If you're on the board
  - Board prep pack generated per meeting.
  - Per item: 1-paragraph summary, BIV traffic light, top 3 risks,
    decision options, estimated board time.
  - Decide in Preflight. Conditions auto-created. Zero meeting minutes.
  
  ### If you're the business
  - Submit your request in one form. Get status updates.
  - No email chains. No hallway conversations that take 3 meetings.
  
  ### If you're the FG/DPO
  - Draft verwerkingsregister entry auto-generated when personal data detected.
  - DPIA drafted from multi-persona assessment. Review and sign off.
  - Your determination is independent — the system enforces it.

## How It Works (30-second version)                    ← NEW (high-level only)
  The pipeline in one diagram:
  Request → Classify → Retrieve context → Assess (personas) → Challenge → Output
  
  [Keep the ASCII pipeline diagram — panel loved it]
  
  Key concepts (brief):
  - 15 personas representing the full EA board + security/privacy/compliance
  - Two modes: Fast (single LLM call, batched) and Deep (per-persona simulation)
  - Three authority types: Security VETO, Risk ESCALATION, FG INDEPENDENT
  - Grounded in ZiRA + hospital's own Archi model + regulatory knowledge base
  
  → Full technical architecture: see ARCHITECTURE.md

## Worked Example: Digital Pathology                   ← NEW (prompt 4.3)
  [Full end-to-end walkthrough]
  
  ### The request
  "We want Digital Pathology from Sysmex"
  
  ### What Preflight does (Step 0-1)
  - Classifies: clinical-system, high impact
  - Selects personas: CIO, CMIO, Marcus, Thomas, Lena, Aisha, Victor, 
    CISO, ISO-Officer, Nadia, FG-DPO, PO + Red Team (high impact)
  - Queries ArchiMate: finds existing pathology capabilities, LIS connections,
    JiveX/PACS dependencies, Cloverleaf routing
  - Queries TOPdesk: related CIs, DR status of LIS, open security risks
  
  ### What the architect sees (Step 2-3)
  - Landscape brief: "3 existing systems in diagnostics capability space..."
  - Persona assessments:
    - CMIO: conditional — IVDR classification needed, Cloverleaf integration 
      for pathology results, clinical validation requirement
    - Thomas: concern — portfolio overlap with existing pathology capabilities,
      vendor viability assessment needed
    - Victor: conditional — STRIDE needed, whole-slide imaging = large data,
      DICOM security
    - Nadia: conditional — AIVG Module ICT compliance, verwerkersovereenkomst,
      bijzondere persoonsgegevens processing
    - FG-DPO: DRAFT DETERMINATION pending review — patient tissue images are
      bijzondere persoonsgegevens, verwerkingsgrondslag needed
  
  ### What the board gets (Step 5)
  [Show the actual PSA output — abbreviated but real]
  
  ### What happens after
  - Board approves with 4 conditions
  - Conditions tracked in Preflight
  - Vendor intelligence profile created for Sysmex
  - Architecture debt item: "decommission legacy pathology workflow"

## The Personas                                        ← KEEP but restructure
  [Table of 15 core personas — move Erik/Petra to "Optional Extensions"]
  [Each persona: role, name, what they check, special authority]
  [Remove the full incentives/constraints text — that stays in the .mjs file]
  
  ### Core (always available)
  CIO, CMIO, Marcus, Sophie, Thomas, Lena, Jan, Aisha, Victor,
  CISO, ISO-Officer, Nadia, FG-DPO, PO, Raven
  
  ### Extensions (activate when relevant)
  Erik (Manufacturing & OT), Petra (R&D & Engineering Design)
  
  ### Persona Authority Model
  | Authority | Persona | Effect | Can be overruled? |
  | VETO | Victor | Pipeline stops | Yes, by board with documented rationale |
  | ESCALATION | Nadia | Upgrades to deep review | Yes, by senior management |
  | DETERMINATION | FG-DPO | Processing cannot proceed | No (AVG Art. 38(3)) |
  | PATIENT SAFETY | CMIO | Minimum standard review | No fast-track for clinical |
  | CHALLENGE | Raven | Stress-tests assessments | N/A — advisory only |
  
  Note: All authority persona outputs are DRAFTS requiring human confirmation.
  The real Victor/Nadia/FG reviews and signs off.

## Architecture Products                               ← KEEP but add templates
  [Table of 9 products — add Integration Design, Clinical Impact Brief]
  [Each product links to its template in templates/]
  
  Product selection logic:
  Every assessment → PSA + ADR
  Clinical system  → + Clinical Impact Brief
  New vendor       → + Vendor Assessment
  Personal data    → + DPIA + verwerkingsregister draft
  Business-critical→ + BIA/BIV
  Integration      → + Integration Design
  High security    → + Security Assessment (standalone)
  New technology   → + Tech Radar Update

## The Full Lifecycle                                  ← NEW (prompt 3.1)
  State machine: what states can a request be in?
  
  ```
  SUBMITTED → PRELIMINARY → CLARIFICATION → ASSESSED → 
  BOARD-READY → IN-REVIEW → DECIDED → CONDITIONS-OPEN → CLOSED
  ```
  
  ### Condition tracking
  [From prompt 3.2 — owner, due date, evidence, source persona]
  
  ### Delta re-assessment  
  [From prompt 3.3 — what changed, which personas re-evaluate, diff view]
  
  ### Institutional memory
  [From prompt 3.4 — similar past assessments, vendor intelligence, debt register]

## Triage Logic                                        ← KEEP but add floors
  [determineTriageLevel() with added clinical/patient-data/OT floors]
  
  Hard floors (cannot be fast-tracked):
  - clinical-system → minimum standard review, CMIO always active
  - patient-data → FG-DPO always active
  - OT-boundary detected → Erik always active

## How Architects' Roles Change                        ← NEW (prompt 4.7)
  [Honest about the shift. Amplification, not replacement.
   Senior architects benefit most — judgment, not grind.]

## Accountability Model                                ← NEW (prompt 4.14)
  [Every output states: draft assessment, architect owns final, board owns decision.
   Human-in-the-loop for all authority determinations.]

## Why Not Power Platform?                             ← NEW (prompt 4.8)
  [Analytical comparison, not ideological dismissal]

## Build Phases                                        ← REWRITE (prompt 4.6)
  ### Phase 1 — Useful on Day One (2-4 weeks)
  Input: business request + Archi model
  Output: landscape brief + ZiRA positioning + batched assessment + draft PSA
  Stack: FastAPI + single LLM + Archi parser + PostgreSQL (pgvector)
  NOT included: deep mode, document parsing, Milvus, frontend, auth
  
  ### Phase 2 — Grounded (months 2-3)
  Add: TOPdesk + SharePoint/OneDrive + document parsing + embedding pipeline
  Add: Entra ID auth + RBAC/ABAC + audit trail
  Add: self-service intake portal
  
  ### Phase 3 — Deep (months 3-4)
  Add: simulatePanel() deep mode + interaction rounds
  Add: Challenge step (veto/escalation/FG/Red Team)
  Add: All 9 architecture products with bilingual templates
  
  ### Phase 4 — The Platform (months 4-6)
  Add: Next.js frontend + condition tracking + board prep packs
  Add: vendor intelligence + debt register + compliance dashboard
  
  ### Phase 5 — Learn (ongoing, non-optional)
  [Explicitly non-optional — without this, Preflight is a document generator,
   not a learning system]

## Success Metrics                                     ← KEEP but add baselines
  [Add current-state baselines per Sophie's feedback]
  [Add kill metric per Raven: if false-fast-track >10% after 3 months, kill it]

## What Preflight Leaves to Humans                     ← KEEP (panel loved this)

## Estimated Footprint                                 ← REWRITE (prompt 4.5)
  [Be honest about actual size. Don't say 800 lines when it's 40+ files.]
```

---

## ARCHITECTURE.md — New Technical Document

Everything the domain architects and developers need. Moved from PREFLIGHT.md.

```markdown
# Preflight — Technical Architecture

## NemoClaw Framework
  [LLM Strategy, LLM Router, tiered reasoning]

## Pipeline Implementation
  ### Step 0 — Ingest (detailed)
  ### Step 1 — Classify (detailed, including classification validation strategy)
  ### Step 2 — Retrieve (detailed)
  ### Step 3 — Assess (detailed, including prompt template design)
  ### Step 4 — Challenge (detailed)
  ### Step 5 — Output (detailed)

## Prompt Engineering Strategy                          ← NEW (prompt D1 from v1)
  [System prompt templates, few-shot examples, output format enforcement]
  [Hallucination mitigation: citation verification against knowledge base]
  [Prompt injection defense for document parsing pipeline]
  [Output deduplication across personas]

## ArchiMate Parser
  [Scope: which elements, relationships, layers, viewpoints]
  [Traversal depth: direct + indirect for cascade analysis]
  [Hospital model vs. ZiRA model: conflict resolution]

## Principetoets Methodology                           ← NEW (prompt 4.9)
  [How qualitative principles are evaluated]
  [Waardevol weighted highest per Sophie]

## Document Parsing Pipeline
  [Workhorse + Smart tiers — moved from PREFLIGHT.md]

## Embedding Pipeline
  [Four strategies, embedding models, Milvus architecture — moved]

## Knowledge Base
  [Corpus structure, maintenance, re-indexing]

## Authentication & Authorization
  [Entra ID, OAuth 2.1, RBAC roles, ABAC policies]

## Audit Trail
  [Schema, hash chain, NEN 7513, SIEM integration]

## Deployment Architecture                             ← NEW (prompt B1 from v1)
  [Where components run, network topology, sizing]

## Integration Architecture                            ← NEW (prompt B3 from v1)
  [How Preflight connects to external systems]
  [Integration diagram, error handling, token management]
  [LeanIX integration — NEW per Thomas]

## API Specification                                   ← NEW (prompt B4 from v1)
  [OpenAPI spec outline for Preflight's own API surface]

## Testing & Validation Strategy
  [Tier 1: deterministic, Tier 2: evaluation, Tier 3: end-to-end]
  [Validation protocol with 5 real proposals]
  [Kill metric]

## Dogfooding
  [Personas assess Preflight's own decisions]

## Repository Structure
  [Planned directory layout]
```

---

## Prompt-to-Section Mapping

Where each v2 prompt lands in the new documentation:

| Prompt | Lands in | Section |
|--------|----------|---------|
| **Priority 1** | | |
| 1.1 Redesign Phase 1 | PREFLIGHT.md | Build Phases → Phase 1 |
| 1.2 First-run experience | PREFLIGHT.md | What You Get → If you're an architect |
| 1.3 Validation protocol | ARCHITECTURE.md | Testing & Validation Strategy |
| 1.4 New hospital day one | PREFLIGHT.md | What You Get (opening scenario) |
| **Priority 2** | | |
| 2.1 PSA draft experience | DIGITAL-PATHOLOGY.md | Full worked example |
| 2.2 Board prep pack | PREFLIGHT.md | What You Get → If you're on the board |
| 2.3 Portfolio overlap | PREFLIGHT.md | What You Get → If you're an architect |
| 2.4 Cascade analysis | templates/integration-design.md | Cascade analysis section |
| 2.5 AIVG vendor checklist | templates/vendor-assessment.md | AIVG checklist section |
| 2.6 Clinical impact brief | templates/clinical-impact.md | New template |
| 2.7 Verwerkingsregister draft | templates/dpia.md | Auto-generated register entry |
| 2.8 STRIDE pre-fill | templates/security-assessment.md | Pre-fill methodology |
| 2.9 Vendor intelligence | PREFLIGHT.md | The Full Lifecycle → Institutional memory |
| **Priority 3** | | |
| 3.1 Request lifecycle | PREFLIGHT.md | The Full Lifecycle |
| 3.2 Condition lifecycle | PREFLIGHT.md | The Full Lifecycle → Condition tracking |
| 3.3 Delta re-assessment | PREFLIGHT.md | The Full Lifecycle → Delta re-assessment |
| 3.4 Institutional memory | PREFLIGHT.md | The Full Lifecycle → Institutional memory |
| 3.5 Debt visualization | PREFLIGHT.md | The Full Lifecycle → Institutional memory |
| **Priority 4** | | |
| 4.1 Split documents | PREFLIGHT.md + ARCHITECTURE.md | Structure itself |
| 4.2 Move technical details | ARCHITECTURE.md | All technical sections |
| 4.3 Digital Pathology example | DIGITAL-PATHOLOGY.md | Entire document |
| 4.4 Reduce persona set | PREFLIGHT.md | The Personas |
| 4.5 Fix footprint estimate | PREFLIGHT.md | Estimated Footprint |
| 4.6 Realistic timeline | PREFLIGHT.md | Build Phases |
| 4.7 Role change section | PREFLIGHT.md | How Architects' Roles Change |
| 4.8 Power Platform justification | PREFLIGHT.md | Why Not Power Platform? |
| 4.9 Principetoets methodology | ARCHITECTURE.md | Principetoets Methodology |
| 4.10 Integration Design template | templates/integration-design.md | New template |
| 4.11 Human-in-the-loop FG | PREFLIGHT.md | Accountability Model |
| 4.12 Clinical triage floor | PREFLIGHT.md | Triage Logic |
| 4.13 LeanIX integration | ARCHITECTURE.md | Integration Architecture |
| 4.14 Accountability model | PREFLIGHT.md | Accountability Model |

---

## What Gets Removed from Current PREFLIGHT.md

| Current Section | Action |
|----------------|--------|
| NemoClaw framework details | → ARCHITECTURE.md |
| LLM Router code examples | → ARCHITECTURE.md |
| Components table | → ARCHITECTURE.md |
| Auth/AuthZ detailed design | → ARCHITECTURE.md |
| Audit trail schema (SQL) | → ARCHITECTURE.md |
| Document parsing pipeline details | → ARCHITECTURE.md |
| Embedding pipeline (4 strategies) | → ARCHITECTURE.md |
| Milvus indexing architecture | → ARCHITECTURE.md |
| Fallback chain | → ARCHITECTURE.md |
| SIEM integration details | → ARCHITECTURE.md |
| SOC 2 readiness section | Remove entirely (premature) |
| Full persona incentives/constraints | Stay in .mjs file, summary in PREFLIGHT.md |
| Testing Tier 1/2/3 details | → ARCHITECTURE.md |
| Estimated Footprint "800-1000 lines" | Rewrite honestly |

## What Gets Added to PREFLIGHT.md

| New Section | Source Prompt |
|-------------|-------------|
| What You Get (per-role experience) | 1.2, 1.4 |
| Worked Example: Digital Pathology | 4.3 |
| The Full Lifecycle (state machine) | 3.1, 3.2, 3.3, 3.4 |
| Persona Authority Model (with human-in-the-loop) | 4.11 |
| Triage floors (clinical, patient-data, OT) | 4.12 |
| How Architects' Roles Change | 4.7 |
| Accountability Model | 4.14 |
| Why Not Power Platform? | 4.8 |
| Kill metric | Raven |

---

## Execution Plan

| Step | What | Produces |
|------|------|---------|
| 1 | Execute prompts 4.1 + 4.2 | Split PREFLIGHT.md → PREFLIGHT.md (product) + ARCHITECTURE.md (technical) |
| 2 | Execute prompt 4.3 | DIGITAL-PATHOLOGY.md (worked example) |
| 3 | Execute prompts 1.1 + 4.6 | Rewrite Build Phases with realistic Phase 1 |
| 4 | Execute prompts 1.2 + 1.4 | Write "What You Get" section |
| 5 | Execute prompts 2.1-2.9 | Design each "makes you look good" experience, update What You Get |
| 6 | Execute prompts 3.1-3.5 | Write "The Full Lifecycle" section |
| 7 | Execute prompts 4.4-4.14 | All remaining document improvements |
| 8 | Execute prompt 1.3 | Write validation protocol in ARCHITECTURE.md |
| 9 | Create template files | templates/*.md from existing content + new templates |
| 10 | Re-run MiroFish panel | Validate: do the personas now say "I need this"? |
