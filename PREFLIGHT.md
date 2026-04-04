# Preflight

**"Run it through Preflight."**

An EA intake and pre-assessment tool that does the analytical homework — from the moment the business asks for something, through to a board-ready package. It doesn't replace the EA board. It prepares the EA board.

---

## The Problem

Today, when the business says "we want X":

1. An architect gets assigned
2. They spend days/weeks gathering context — what does it do, what does it connect to, where does it sit in the landscape, what data does it handle, does it overlap with something we have
3. They write up an initial assessment
4. It goes to the board
5. The board asks questions the architect didn't think to cover
6. Back to step 2

The cycle time from business request to architectural decision is weeks to months. Most of that time is spent on structured, repeatable analytical work — not judgment.

## What It Is Not

- Not an EA board simulator
- Not a decision-maker
- Not a multi-agent system pretending to deliberate
- Not a Copilot Studio chatbot

---

## What You Get

### If you're an architect

You paste a business request — even a single sentence like "we want Digital Pathology from Sysmex." Preflight does what you'd spend days doing manually:

1. **Queries your hospital's Archi model** — finds existing applications in this capability space, overlaps, lifecycle status, serving/flow/triggering relationships, interfaces, dependencies
2. **Queries TOPdesk** — related CIs, hosting patterns, DR status, open security risks, vendor due diligence
3. **Maps to ZiRA** — positions the proposal in the bedrijfsfunctiemodel, informatiedomeinenmodel, dienstenmodel, and procesmodel
4. **Runs persona assessments** — 8-12 domain perspectives evaluate the proposal from their lens
5. **Produces a draft PSA** — ZiRA positioning pre-filled, principetoets drafted, domain assessments attributed to named personas, risk register populated, conditions for approval listed, open questions for the board identified
6. **Generates diagrams** — integration flows (Mermaid sequence diagrams), cascade dependencies (Mermaid flowcharts), landscape position (draw.io, editable), data flows for DPIA, STRIDE attack surface. All grounded in actual ArchiMate relationships, not guessed. Edit the draw.io diagrams for your board presentation.

You spend an hour refining. The board receives a PSA that would have taken you a week.

If it's straightforward (simple SaaS, no patient data, no integration complexity), Preflight tells you: "Fast-track candidate. Full assessment optional." You don't waste pipeline resources on a €5k employee survey tool.

**Point it at your document folder.** Every architect has one — vendor PDFs, policies, board decisions, contracts, data sheets. Point Preflight at the folder. It parses everything, auto-classifies (regulatory, vendor, hospital policy, architecture), tags persona relevance (which chunks Victor should see vs. Nadia vs. Thomas), and indexes it all. No manual curation. Drop a folder, get a knowledge base. Turn on `--watch` and it stays current as docs change.

### If you're on the board

Thursday afternoon before the board meeting. You open Preflight and see:

- **5 proposals** on the agenda
- **Estimated board time**: 2.5 hours
- **1 item flagged high-risk**: BIV 3-3-3, security veto pending

Per item:
- One-paragraph executive summary in business language
- BIV classification with traffic light (red/amber/green)
- Top 3 risks with severity, sourced from named personas
- Recommended board time (15 min / 30 min / full session)
- Decision options: approve / approve with conditions / reject / defer
- Draft conditions pre-filled from persona assessments

After the meeting:
- Record decisions per item in Preflight
- Conditions auto-created with owners and due dates
- Assessment status updated
- Zero meeting minutes to write

### If you're the business

You submit your request in one guided form. Not email, not Teams, not a hallway conversation that takes 3 meetings to turn into a proper request.

**Base fields**: What do you want? Why? (business problem, not solution). Who is the business sponsor? Expected users. Target go-live. Attach any documents you have.

**Adaptive fields** (appear based on answers): Does this involve patient data? → triggers privacy/clinical routing. Does it connect to existing systems? → triggers integration assessment. New vendor? → triggers vendor evaluation and AIVG compliance.

You get status updates. You see when your request is assessed, when it goes to the board, and what the decision is. No black box.

### If you're the FG/DPO

When Preflight detects personal data in a proposal — patient data, employee data, bijzondere persoonsgegevens — it auto-generates:

- **Draft verwerkingsregister entry**: welke persoonsgegevens, welke betrokkenen, welk doel, welke grondslag, welke bewaartermijn, welke ontvangers
- **DPIA draft** grounded in multi-persona assessment: data flows with classification, processing grounds, risks, mitigations
- **FG determination workflow**: draft assessment pending your review and sign-off

Your determination is independent — the system enforces AVG Article 38(3). If you determine the processing is unlawful, the pipeline stops. Not a veto that can be escalated. A legal determination that requires the proposal to change.

### If you're the security architect

You open an assessment and see a **STRIDE threat model pre-filled** with the proposal's actual components — the specific applications from ArchiMate, the specific interfaces, the specific data flows. Not a generic template. A threat model that already knows the attack surface.

Your veto is real. If you block, the pipeline stops, your conditions become mandatory requirements, and the output is shaped as a rejection with remediation path.

### If you're risk & compliance

You see a **structured regulatory applicability matrix**: which NEN standards apply, AIVG 2022 compliance status, verwerkersovereenkomst status, NIS2 implications. For vendor proposals: an **interactive AIVG 2022 + Module ICT checklist** pre-filled where Preflight already has answers from vendor docs, with evidence fields and sign-off. Walk through it with the vendor. Retire the Excel.

---

## How It Works

Preflight runs every request through a six-step persona-driven pipeline:

```
┌───────────────────────────────────────────────────────────┐
│                        PREFLIGHT                           │
│                                                           │
│  ┌───────────┐  Personas ask:                             │
│  │ Step 0    │  "What would each role want to know        │
│  │ INGEST    │   before they can even begin to assess?"   │
│  │           │  → drives ArchiMate/TOPdesk queries        │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas determine:                       │
│  │ Step 1    │  "Who needs to be in the room for this?"   │
│  │ CLASSIFY  │  → selects 8-12 personas                  │
│  │           │  → regulatory triggers activate            │
│  │           │    CMIO, Risk, Security automatically      │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas drive:                           │
│  │ Step 2    │  "What does each selected persona need     │
│  │ RETRIEVE  │   to see to do their job?"                 │
│  │           │  → per-persona RAG retrieval, not global   │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Personas evaluate:                        │
│  │ Step 3    │  Fast: batched single LLM call             │
│  │ ASSESS    │  Deep: per-persona calls + interaction     │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Authority personas act:                   │
│  │ Step 4    │  Security (Victor) → VETO if block         │
│  │ CHALLENGE │  Risk (Nadia) → ESCALATE if block          │
│  │           │  FG/DPO → DETERMINATION if unlawful        │
│  │           │  CMIO → PATIENT SAFETY floor               │
│  │           │  Red Team → pre-mortem on assessments       │
│  └─────┬─────┘                                            │
│        │                                                  │
│  ┌─────▼─────┐  Output:                                   │
│  │ Step 5    │  Draft architecture products                │
│  │ OUTPUT    │  Every finding attributed to a persona     │
│  │           │  Bilingual: NL/EN                          │
│  └───────────┘                                            │
└───────────────────────────────────────────────────────────┘
```

**Two assessment modes:**

| Impact | Mode | What happens |
|--------|------|-------------|
| Low / Medium | Fast (batched) | All perspectives in one prompt, one LLM call. Quick triage. |
| High / Critical | Deep (panel) | Each persona gets its own call. Responds in character. Optional interaction round: personas see each other's reactions. Then synthesis. |

→ Full technical pipeline design: see [ARCHITECTURE.md](ARCHITECTURE.md)

---

## The Personas

Defined in `personas/ea-council-personas.mjs`. Each carries: `role`, `name`, `incentives`, `constraints`, `domain`, `history` (injected at runtime with landscape data).

### Core Personas

| Persona | Name | What They Check | Special Authority |
|---------|------|----------------|-------------------|
| Chief Information Officer | CIO | Budget, strategy, TCO, staffing, vendor consolidation, shadow IT | Budget & strategy gate |
| Chief Medical Information Officer | CMIO | Patient safety, clinical workflows, HL7v2/FHIR, Cloverleaf, JiveX, Digizorg | **Patient safety floor** |
| Chief Architect | Marcus | ZiRA coherence, capability map, architecture debt, ADR register, principetoets | Final recommendation |
| Solution Architecture | Marco | Implementability, NFRs, solution design, delivery approach, team capability | — |
| Business Architecture | Sophie | Strategy alignment, bedrijfsfunctiemodel, dienstenmodel, waardepropositie, organizational change | — |
| Business Process Architecture | Joris | BPMN, process impact, as-is/to-be, handovers, bottlenecks, clinical pathways, exception handling | — |
| Application Architecture | Thomas | Portfolio overlap, tech radar, build/buy/SaaS, AIVG exit clauses, vendor viability | — |
| Integration Architecture | Lena | API standards, coupling risk, data flows, cascade dependencies, integration effort | — |
| Information Architecture | Daan | Information model, zibs, semantic interoperability, master data, information ownership | — |
| Technology & Infrastructure | Jan | Hosting, DR, RPO/RTO, capacity, operational readiness, who's on-call | — |
| Network & Communications | Ruben | Network zones, segmentation, bandwidth, latency, clinical network isolation | — |
| Data & AI Architecture | Aisha | Data classification, GDPR/DPIA, data lineage, EU AI Act, data quality | — |
| Security Architecture | Victor | STRIDE, zero trust, IAM, encryption, SBOM, supply chain security | **VETO power** |
| CISO | CISO | Strategic security risk, SOC capacity, threat landscape, risk acceptance | — |
| Information Security Officer | ISO-Officer | NEN 7510 ISMS, vulnerability management, patch cycles, monitoring capacity | — |
| Risk & Compliance | Nadia | AVG/GDPR, NEN 7510/7512/7513, AIVG 2022, NIS2, MDR/IVDR, EU AI Act | **ESCALATION power** |
| FG / Data Protection Officer | FG-DPO | Verwerkingsgrondslag, DPIA, rechten betrokkenen, doorgifte, lawfulness | **INDEPENDENT** |
| Privacy Officer | PO | Privacy by design/default, data minimization, verwerkingsregister, DPIA execution | — |
| Enterprise Portfolio Architecture | Femke | Architecture roadmap, capability gaps, target architecture, transition planning, architecture KPIs | — |
| Red Team | Raven | Hidden assumptions, failure modes, groupthink, pre-mortem | Challenge only |

### Optional Extensions

| Persona | Name | When Activated | What They Check |
|---------|------|---------------|----------------|
| Manufacturing & OT | Erik | OT boundary detected in proposal | ISA-95, IEC 62443, production continuity |
| R&D & Engineering Design | Petra | Export control or PLM impact detected | IP protection, export control (EAR/ITAR/EU dual-use), HPC |

### Persona Authority Model

| Authority | Persona | Effect | Can be overruled? | Human confirmation |
|-----------|---------|--------|-------------------|-------------------|
| VETO | Victor (Security) | Pipeline stops. Conditions become mandatory. | Yes, by board with documented rationale | Real security architect reviews and signs off |
| ESCALATION | Nadia (Risk) | Upgrades to deep review. Board treatment changes. | Yes, by senior management | Real compliance officer reviews and signs off |
| DETERMINATION | FG-DPO | Processing cannot proceed until lawful. | **No** (AVG Article 38(3)) | Real FG reviews and signs off |
| PATIENT SAFETY | CMIO | Cannot be fast-tracked. Minimum standard review. | No fast-track for clinical systems | Real CMIO reviews clinical findings |
| CHALLENGE | Raven (Red Team) | Stress-tests other assessments. Advisory. | N/A | Architect reviews findings |

**All authority persona outputs are drafts requiring human confirmation.** The LLM generates the analysis. The real person owns the determination.

### Persona Routing

Not every request needs 15 opinions. `selectRelevant()` maps request type to persona subset:

| Request Type | Who's in the Room |
|-------------|-------------------|
| `new-application` | CIO, Marcus, Sophie, Thomas, Lena, Jan, Aisha, Victor, ISO-Officer, Nadia, FG-DPO, PO |
| `clinical-system` | CIO, CMIO, Marcus, Thomas, Lena, Aisha, Victor, CISO, ISO-Officer, Nadia, FG-DPO, PO |
| `vendor-selection` | CIO, Marcus, Thomas, Lena, Victor, CISO, ISO-Officer, Nadia, FG-DPO, PO |
| `infrastructure-change` | Marcus, Jan, Victor, ISO-Officer, Nadia |
| `integration` | Marcus, Thomas, Lena, Victor, ISO-Officer, Nadia |
| `data-platform` | Marcus, Aisha, Jan, Victor, ISO-Officer, Nadia, FG-DPO, PO |
| `ai-ml` | CIO, Marcus, Aisha, Thomas, Victor, CISO, Nadia, FG-DPO, PO |
| `decommission` | Marcus, Thomas, Lena, Jan, Nadia, FG-DPO |

**Governance baseline**: Marcus, Victor, Nadia, and FG-DPO are always in the room (fallback for unknown types).

**Red Team**: activates only for high/critical impact proposals.

**Hard triage floors** (cannot be overridden by classification):
- `clinical-system` → minimum standard review, CMIO always active
- `patient-data` detected → FG-DPO and PO always active
- OT boundary detected → Erik always active

---

## Architecture Products

Preflight generates **draft architecture products** — the documents architects actually spend their time creating. Not final versions. Drafts grounded in landscape data, persona assessments, and ZiRA, ready for the architect to refine and own.

| Product | NL Name | When Generated | Primary Personas |
|---------|---------|----------------|------------------|
| **Project Start Architecture** | Project Start Architectuur (PSA) | Every assessment | All selected |
| **Architecture Decision Record** | Architectuurbesluit (ADR) | Every decision point | Marcus + relevant domain |
| **Clinical Impact Brief** | Klinisch Impactoverzicht | Clinical system proposals | CMIO |
| **Process Impact Assessment** | Procesimpactanalyse | Process-changing proposals | Joris, CMIO (clinical pathways) |
| **Vendor/Product Assessment** | Leveranciers-/Productbeoordeling | New vendor/product | CIO, Thomas, Lena, Victor, Nadia |
| **Data Protection Impact Assessment** | Gegevensbeschermingseffectbeoordeling (DPIA) | Personal/patient data involved | Aisha, Victor, Nadia, CMIO |
| **Business Impact Analysis + BIV** | Bedrijfsimpactanalyse (BIA) + BIV-classificatie | Business-critical systems | Jan, Victor, Nadia, CIO, CMIO |
| **Integration Design** | Integratieontwerp | Systems need to connect | Lena, CMIO (clinical), Jan, Ruben |
| **Network Impact Assessment** | Netwerkimpactanalyse | New traffic patterns introduced | Ruben, Jan |
| **Security Assessment** | Beveiligingsbeoordeling | Every assessment (standalone for high-impact) | Victor |
| **NFR Specification** | Niet-functionele eisen | High-impact proposals, solution handover | Marco, Jan |
| **EU AI Act Risk Classification** | EU AI-verordening risicoclassificatie | AI/ML proposals | Aisha, Nadia |
| **Operational Readiness Checklist** | Operationele gereedheid checklist | Every production system | Jan, Ruben, ISO-Officer |
| **Architecture Roadmap Impact** | Architectuurroadmap impactanalyse | Multiple related proposals, roadmap deviation | Femke, Marcus |
| **Tech Radar Update** | Technologieradar Update | New technology enters landscape | Thomas |

**Product selection logic:**

```
Every assessment         → PSA (always) + ADR (always)
Clinical system          → + Clinical Impact Brief + Process Impact
New vendor/product       → + Vendor Assessment
Personal/patient data    → + DPIA + verwerkingsregister draft
Business-critical        → + BIA/BIV + Operational Readiness + NFR Specification
System integration       → + Integration Design + Network Impact
Process-changing         → + Process Impact Assessment
AI/ML system             → + EU AI Act Risk Classification
High security impact     → + standalone Security Assessment
New technology           → + Tech Radar Update
Roadmap deviation        → + Architecture Roadmap Impact
Decommission             → + Decommission Impact (cascade, data migration, interface sunset)
Production deployment    → + Operational Readiness Checklist
Solution handover        → + NFR Specification
```

All products are bilingual (NL/EN). Language is set per assessment. ZiRA terminology is Dutch-native. Templates: see [templates/](templates/).

---

## The Full Lifecycle

Preflight isn't useful as a side tool. It owns the full lifecycle from request to resolution.

### Request States

```
SUBMITTED → PRELIMINARY → CLARIFICATION → ASSESSED →
BOARD-READY → IN-REVIEW → DECIDED → CONDITIONS-OPEN → CLOSED
```

| State | What Happens | Who Acts |
|-------|-------------|----------|
| SUBMITTED | Business submits request via intake portal | Business requestor |
| PRELIMINARY | Preflight auto-generates landscape brief + preliminary assessment | Automated |
| CLARIFICATION | Preflight identifies what's missing per persona, generates follow-up questions | Requestor answers |
| ASSESSED | Architect reviews, refines, adds judgment to the draft assessment | Architect |
| BOARD-READY | Assessment finalized, added to next board prep pack | Architect |
| IN-REVIEW | Board reviews in meeting | Board |
| DECIDED | Board records decision: approve / conditional / reject / defer | Board chair |
| CONDITIONS-OPEN | Conditions tracked with owners, due dates, evidence | Condition owners |
| CLOSED | All conditions met or waived. Assessment fully cleared. | Architect confirms |

### Conversational Clarification

Before running the full assessment, Preflight identifies what's missing based on the selected personas' requirements:

```
Request: "We want Digital Pathology from Sysmex"

Missing context (per persona):
  CMIO:    "Will this replace or supplement existing pathology workflows?"
  Victor:  "Is this cloud-hosted or on-premises? Where is data stored?"
  Nadia:   "Will patient samples or data cross organizational boundaries?"
  Thomas:  "Do we already have pathology capabilities in the landscape?"
  FG-DPO:  "What categories of patient data? What is the verwerkingsgrondslag?"
  Lena:    "How will results flow back to the EPD? HL7v2 or FHIR?"
```

The architect or requestor answers. Then the assessment runs with complete context. This eliminates the "board asks questions → back to research → re-assess" loop.

### Condition Tracking

Every approved assessment creates condition records. No more conditions living in meeting minutes, email, and memory.

| Field | Purpose |
|-------|---------|
| Condition | What must be done (from persona's conditions for approval) |
| Source persona | Who raised it (e.g., "Victor: complete STRIDE threat model") |
| Owner | Who is responsible |
| Due date | When it must be completed |
| Status | Open / in progress / completed / overdue / waived |
| Evidence | How completion is demonstrated |

**Dashboard**: overdue conditions highlighted, approaching due dates (7 days, 1 day), per-assessment status, per-owner workload, board view of open conditions, trend over time.

### Delta Re-Assessment

When a proposal changes after board feedback, the architect marks what changed. Preflight diffs and only re-evaluates affected personas:

```
Change: "Vendor changed hosting from US to EU"
  Re-evaluate: Nadia (data residency), Victor (threat landscape), FG (doorgifte)
  Carry forward: Thomas, Lena, Sophie, CMIO, Jan — unchanged

Change: "Added FHIR interface to EPD"
  Re-evaluate: Lena (new integration), CMIO (clinical interop), Victor (attack surface)
  Carry forward: CIO, Sophie, Nadia — unchanged
```

Board sees: "v2 addresses conditions 1 and 3 from board's v1 feedback."

This eliminates the most time-consuming part of the current process: the iteration loop.

### Institutional Memory

Preflight gets smarter with every assessment. After 50 assessments, it knows the hospital better than any individual architect. When an architect leaves, their knowledge stays. When a new architect starts, they have institutional memory from day one.

**Similar past assessments**: Semantic similarity search over previous assessments. Match score, board decision, conditions set, which conditions are still open. Cross-assessment impact detection: "Assessment #42 and #45 compete for the same capability space. Board should review together."

**Vendor intelligence**: Cumulative vendor profiles. Previous assessments, board decisions, AIVG compliance status, NEN 7510 certification, verwerkersovereenkomst lifecycle (signed date, expiry, sub-processor list, BOZ conformity, last review), contract expiry alerting, number of systems in landscape, open conditions. When an architect leaves, their vendor knowledge stays.

**Architecture debt register**: Every assessment identifies debt. Linked to ArchiMate elements. Categorized: technical / integration / security / compliance / portfolio. Visualized as heat map on the capability model — where is debt concentrated? When a new proposal comes in: "This resolves debt item #47 but creates new debt item #102." Principle violation trends: "ZiRA principle 9 (Eenvoudig) violated in 60% of proposals — portfolio is getting more complex, not simpler."

**Solution pattern library**: After 50 assessments, query: "Show me all solutions that used Cloverleaf for DICOM routing — which worked, which failed, why." Pattern reuse across assessments prevents repeating mistakes.

**Information ownership registry**: Persistent registry of which system is authoritative for which information object. "Medicatieoverzicht — authoritative source: EPD, owner: Apotheek, consumers: 7 systems." Every assessment checks new systems against this registry and flags competing authorities.

**Verwerkingsregister**: Cumulative register of all processing activities identified across assessments. DPIA drafts accumulate into a master register. Queryable. AP audit-ready within 24 hours.

**Architecture KPIs** (computed from assessment history): percentage of landscape aligned with target architecture, architecture debt trend, standards compliance rate, roadmap delivery rate, BIV distribution, false fast-track rate, board agreement rate, condition close rate.

**Natural language query**: "Show me all assessments Victor blocked in the last 6 months." "Which vendor has the most open conditions?" "What architecture debt is linked to the EPD?" "Which ZiRA principles are most commonly violated?"

### Always-On Landscape Tools

These features work outside the assessment pipeline — persistent tools the architect uses daily.

**Cascade dependency graph**: `preflight cascade --system "Labosys"` — instant blast radius for any system in the ArchiMate model, always current. Not just for new proposals. For DR planning, patching coordination, change advisory boards, and incident response.

**Capacity impact overlay**: When a new proposal adds storage or bandwidth demand, overlay against current utilization. "Sysmex adds 15-45 TB/year. Current SAN capacity: 78% utilized. Threshold breach in 8 months."

**DR tier dashboard**: How many Tier 1/2/3 systems does the hospital have? Can the DR infrastructure handle another B=3 system? Distribution across the portfolio.

---

## Triage Logic

`determineTriageLevel()` aggregates persona ratings into board treatment:

| Condition | Treatment |
|-----------|-----------|
| FG determines unlawful | **Rejected** — cannot proceed until lawful (not overridable) |
| CMIO flags patient safety risk | **Minimum standard review** (cannot be fast-tracked) |
| Victor blocks | Deep review (veto) |
| Nadia blocks | Deep review (escalation) |
| Any persona blocks | Deep review |
| 2+ personas have concerns | Standard review |
| All approve/conditional, ≤2 conditionals | Fast-track candidate |

**Quick Scan** (pre-screening): A 30-second lightweight check before committing to a full assessment. Single LLM call:

```
Input: "SaaS tool for employee satisfaction surveys, no patient data, 50 users, €5k/year"
Output: Classification: new-application (low impact). Fast-track candidate. Full Preflight optional.

Input: "AI-powered radiology triage system from startup vendor"
Output: Classification: clinical-system + ai-ml (critical impact). Full Preflight mandatory, deep review expected.
```

---

## BIV Classification

Every system/proposal gets a BIV classification — the Dutch standard for the CIA triad. Each dimension scored independently.

| Dimensie | Question | Scored by |
|----------|----------|-----------|
| **B** — Beschikbaarheid | How long can this be unavailable before patient care or operations is impacted? | Jan, CMIO |
| **I** — Integriteit | What if data is incorrectly modified, corrupted, or incomplete? | Aisha, CMIO, Victor |
| **V** — Vertrouwelijkheid | What if data is accessed by unauthorized persons? | Victor, Nadia, CMIO |

Highest score per dimension wins (conservative — one persona flagging high overrides others flagging medium).

```
B (Beschikbaarheid):
  Jan scores:  2 (workaround available via failover)
  CMIO scores: 3 (lab results unavailable → clinical decisions delayed)
  → Final B = 3 (CMIO's clinical perspective overrides)
```

| Score | B | I | V |
|-------|---|---|---|
| **3 — Hoog** | >1h uitval: direct patient safety risk | Wrong data → wrong clinical decisions | Breach → medisch beroepsgeheim violated, AP melding required |
| **2 — Midden** | >4h uitval: significant business impact, workaround costly | Wrong data → delays, rework, no direct patient risk | Breach → reputational damage, possible AVG melding |
| **1 — Laag** | >24h uitval: limited impact, manual alternatives | Wrong data → limited impact, easily fixed | Breach → limited impact, no persoonsgegevens |

**BIV cascades through the entire assessment:**

| BIV Score | Triggers |
|-----------|----------|
| B=3 | RPO/RTO ≤ 1 hour, DR plan mandatory, ISO 22301 scope |
| I=3 | Data validation mandatory, audit trail on all mutations |
| V=3 | NEN 7510 full scope, encryption at rest + transit, NEN 7513 logging, ABAC patient-data policy, DPIA required |
| Any = 3 | Full BIA report, board treatment = deep review |

---

## ZiRA Grounding

Preflight is grounded in the **ZiRA (Ziekenhuis Referentie Architectuur)** — the Dutch hospital reference architecture maintained by Nictiz.

Every assessment maps to ZiRA's models:

| ZiRA Model | Used by | Purpose in Preflight |
|------------|---------|---------------------|
| 12 Architectuurprincipes | Marcus | Principetoets (Waardevol, Veilig, Duurzaam, Flexibel, Eenvoudig, etc.) |
| Bedrijfsfunctiemodel | Marcus, Sophie | Map proposal to business functions across 5 domains |
| Dienstenmodel | Sophie | Which diensten are impacted |
| Procesmodel | Sophie, CMIO | Which of the 8 primary care processes are affected |
| Informatiemodel + zibs | Aisha | Information objects, data classification |
| Informatiedomeinenmodel | Marcus, Aisha | Domain boundaries for information governance |
| Applicatiefunctiemodel | Thomas | Vendor-independent application functions per domain |

The ZiRA `.archimate` model is loaded alongside the hospital's own Archi model. Preflight cross-references "what ZiRA says should exist" with "what actually exists in our landscape."

Tracks the transition to **ZaRA** (Zorgaanbieder Referentie Architectuur) — merging ZiRA + RDC + RDGGZ into one care-wide architecture.

**Principetoets methodology**: Each ZiRA principle is evaluated against the proposal using the principle definition and hospital-specific interpretation guidelines from the knowledge base. ZiRA principle 1 (Waardevol) is weighted as primary — if a proposal cannot demonstrate value, other principles are secondary.

---

## Knowledge Base

The knowledge corpus lives as markdown files, chunked and embedded for per-persona retrieval:

```
knowledge/
├── zira/                     # ZiRA reference architecture
├── regulatory/               # NEN 7510/7512/7513/7516/7517, AVG, NIS2, MDR/IVDR, Wegiz, EU AI Act
├── procurement/              # AIVG 2022 + Module ICT
├── hospital/                 # Local principles, policies, standards, tech radar, reference architectures
└── glossary/                 # Terminology (aligned with ZiRA begrippenlijst)
```

Retrieval is persona-scoped: Victor gets security controls, Nadia gets regulatory clauses, Thomas gets tech radar entries. Not a global dump.

→ Full knowledge base design, embedding pipeline, and retrieval architecture: see [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Integrations

**Preflight makes your existing tools useful.** It doesn't replace them — it's the front door they're all missing.

| System | Technology | What Preflight Gets |
|--------|-----------|-------------------|
| **Archi** | .archimate XML parser | Application landscape, capabilities, interfaces, tech stack, relationships, cascade dependencies |
| **TOPdesk** | REST API | CMDB, assets, CIs, change records, open risks, GRC, vendor due diligence |
| **SharePoint** | Microsoft Graph API | Architecture policies, standards, board decisions, reference docs |
| **OneDrive** | Microsoft Graph API | Vendor docs, data sheets, proposal attachments |
| **LeanIX** | API | Application portfolio, lifecycle status, technology risk, business criticality |
| **SIEM** | CEF/syslog | Security events streamed for correlation |

→ Full integration architecture, error handling, and API specification: see [ARCHITECTURE.md](ARCHITECTURE.md)

---

## How Architects' Roles Change

Preflight shifts the architect's role from **analyst** to **editor and judge**.

Today, an architect spends 80% of their time on structured, repeatable analytical work: querying the landscape, gathering policies, checking regulatory applicability, writing up findings domain by domain. The remaining 20% is judgment — the political context, the strategic trade-offs, the "I talked to the department head and she told me they tried this three years ago."

Preflight does the 80%. The architect owns the 20% — and that 20% is why you hired an experienced architect, not a junior analyst.

**This is not a threat to senior architects. It is an amplifier.** The architect who uses Preflight presents the most thorough assessments, catches issues others miss, and has capacity for strategic work because they are not drowning in analytical grind. They are not replaced — they are freed to do the work only they can do.

The risk is real: junior architects may over-rely on Preflight output without applying critical judgment. Mitigation: every Preflight output carries the header **"Draft assessment — the architect owns the final assessment, the board owns the decision."** Shadow mode (Phase 5) calibrates trust before Preflight becomes primary.

---

## Accountability Model

**Preflight provides analysis. The architect provides judgment. The board provides decisions.**

Every output states explicitly:

> *This is a draft assessment generated by AI personas. The architect reviewed and owns the final assessment. The board owns the decision. Preflight is a preparation tool, not a decision-maker.*

When an authority persona produces a finding:
- Victor's STRIDE analysis is a **draft** — the real security architect reviews and signs off
- Nadia's regulatory matrix is a **draft** — the real compliance officer reviews and signs off
- FG-DPO's lawfulness determination is a **draft** — the real FG reviews and confirms
- The CMIO's patient safety assessment is a **draft** — the real CMIO validates clinical reasoning

The human confirmation step is not optional. It is built into the workflow. The UI requires sign-off from the relevant authority role before the assessment can move to BOARD-READY.

### Architect Input Markers

When a persona assessment is generic (because landscape context is missing) or when a finding requires human validation that AI cannot provide, the output explicitly calls it out:

```
### CMIO: CONDITIONAL
Clinical validation studies required for diagnostic equivalence.

[ARCHITECT INPUT NEEDED: Has the pathology department been consulted?
How many pathologists support this transition? Which tissue types
are in scope for the initial deployment?]
```

These markers prevent rubber-stamping. They force the architect to engage with the output rather than forwarding it unchanged to the board. If a PSA still contains `[ARCHITECT INPUT NEEDED]` markers, it cannot move to BOARD-READY.

---

## Why Not Power Platform?

The hospital runs on Microsoft 365. Power Automate, Copilot Studio, and Power Apps are available. Why FastAPI + Next.js?

| Concern | Power Platform | Preflight's approach |
|---------|---------------|---------------------|
| LLM flexibility | Locked to Azure OpenAI / Copilot | Any model via pluggable router (NIM, Ollama, API) |
| Vector search | No native vector DB integration | Milvus or pgvector, per-persona scoped retrieval |
| Persona simulation | Copilot Studio: single bot persona | 15 distinct personas with structured output parsing |
| Deep mode | Not supported (single-turn chat) | Multi-call panel simulation with interaction rounds |
| ArchiMate parsing | No .archimate XML support | Custom parser traversing elements + relationships |
| Audit trail | Dataverse audit (limited, not hash-chained) | Append-only PostgreSQL with hash chain, NEN 7513 compliant |
| Bilingual templates | Possible but manual | Template engine with NL/EN switching, ZiRA terms preserved |
| Cost at scale | Per-user licensing + connector licensing + premium capacity | Self-hosted, marginal cost per assessment |

Power Platform is the right tool for simple workflows with standard connectors. Preflight's requirements — multi-persona LLM simulation, ArchiMate model traversal, persona-scoped RAG, hash-chained audit trail — exceed what Power Platform offers without extensive custom development that would negate its low-code advantages.

---

## Build Phases

Each phase delivers standalone value. The architect can use Phase 1 output on day one.

### Phase 1 — Useful on Day One (2-4 weeks)

**What you get**: Paste a request, get a draft PSA with landscape context and persona assessments.

Build:
- FastAPI service with request intake
- Single LLM (model TBD — start with one, optimize later)
- Load personas from `ea-council-personas.mjs`
- ArchiMate model parser (landscape queries)
- Classification + `selectRelevant()` routing
- Batched PERSPECTIVES assessment (fast mode only)
- Markdown output: landscape brief + draft PSA with persona-attributed findings
- PostgreSQL with pgvector (no Milvus yet)
- Quick Scan pre-screening
- Built-in regulatory knowledge base (ships with distribution, no setup):
  - ZiRA v1.4 (bedrijfsfunctiemodel, informatiedomeinenmodel, procesmodel, 12 principes)
  - NEN 7510 controls (mapped to assessment scenarios)
  - AIVG 2022 + Module ICT (checklist items with guidance)
  - AVG/GDPR (verwerkingsgrondslagen, DPIA triggers, rechten betrokkenen)
  - NIS2 (essential entity requirements for healthcare)
- Document folder ingestion (`preflight ingest <folder>`)

**NOT in Phase 1**: Deep mode, Milvus, frontend UI, auth, audit trail, integrations beyond Archi.

**Validation**: Run 5 real past proposals with known board outcomes. If triage matches board treatment on ≥3 of 5, proceed. If <3, reassess the approach before building further.

**Kill metric**: If after shadow mode testing, false fast-track rate >10% or board agreement <60%, stop and reassess.

### Phase 2 — Grounded + Executive Dashboard (months 2-3)

Add:
- TOPdesk + SharePoint/OneDrive integration (Microsoft Graph), LeanIX bidirectional sync
- Document parsing pipeline, embedding pipeline with persona-scoped retrieval
- Entra ID authentication, RBAC/ABAC authorization
- Audit trail (append-only PostgreSQL, hash chain), BIV classification in output
- **Read-only web dashboard** (pipeline status, board agenda, condition tracking, architecture KPIs) — executives need this to champion adoption
- Cascade dependency graph as always-on tool (`preflight cascade --system`)
- Verwerkingsregister cumulative view

### Phase 3 — Deep + Full Product Suite (months 3-4)

Add:
- `simulatePanel()` deep mode with interaction rounds
- Step 4 challenge chain (veto/escalation/FG/Red Team)
- NeMo Guardrails
- All 15 architecture product templates with bilingual output:
  - Core: PSA, ADR, Clinical Impact Brief, Vendor Assessment, DPIA, BIA/BIV, Integration Design, Security Assessment, Tech Radar Update
  - New: Process Impact Assessment, Network Impact Assessment, NFR Specification, EU AI Act Risk Classification, Operational Readiness Checklist, Architecture Roadmap Impact
- Similar past assessments, delta re-assessment, vendor intelligence profiles
- Information ownership registry, solution pattern library
- NEN 7513 compliance logging, SIEM integration
- Shadow mode testing alongside existing process

### Phase 4 — The Platform (months 4-6)

Add:
- Full Next.js frontend with bilingual UI (replaces read-only dashboard)
- Self-service intake portal, conversational clarification
- Condition tracking with escalation, reminders, and lifecycle reporting
- Board preparation packs with decision recording and besluitenlijst generation
- Architecture debt register with heat map on capability model
- Architecture KPIs dashboard (debt trend, standards compliance, principle violations)
- Compliance dashboard (audit trail, hash verification, NEN 7513 reports, verwerkingsregister)
- Feedback capture (board marks findings as useful/missed/wrong)

### Phase 5 — Learn (ongoing, non-optional)

Without Phase 5, Preflight is a document generator. With Phase 5, it is a learning system.

Build:
- Per-persona accuracy tracking — which personas add value vs. noise?
- Tune persona incentives/constraints based on board feedback
- BIV distribution monitoring (inflation/leniency detection)
- Natural language query interface over all Preflight data
- Stale knowledge detection and alerting
- Reference scenario benchmark maintenance
- Persona versioning (which version produced which assessment — MDR traceability)

---

## Dogfooding

The same personas that evaluate business requests also evaluate every architecture decision made building Preflight. Same `selectRelevant()`, same incentives, same constraints.

| Development Decision | Relevant Personas | What They Check |
|---------------------|-------------------|-----------------|
| "Add Milvus for RAG" | Thomas, Jan, Victor, Nadia | Portfolio impact, infra cost, security, compliance |
| "Store vendor docs" | Victor, Aisha, Nadia | Data classification, encryption, retention |
| "Deploy NIM on GPU" | Jan, Victor, CIO | Cost, DR plan, security hardening, budget |
| "Handle patient data in proposals" | CMIO, Aisha, Victor, Nadia, FG-DPO | Clinical classification, GDPR, encryption, DPIA, audit |

No architecture decision ships without a Preflight assessment of that decision.

---

## What Preflight Leaves to Humans

- Final decision authority
- Political and organizational context
- Budget trade-offs and funding decisions
- Vendor relationship considerations
- Strategic bets ("we know this is risky but we're doing it anyway")
- Accountability for outcomes
- Overriding Preflight's recommendation with documented rationale

These are surfaced in every output under **"Open Questions for the Board"** so the board knows exactly what still needs human judgment.

---

## Success Metrics

| Category | Metric | Target | Kill Zone |
|----------|--------|--------|-----------|
| **Speed** | Time from request to first assessment | < 5 minutes | |
| **Speed** | Time from intake to board-ready | < 1 day | |
| **Quality** | Board agreement with triage | >80% | <60% |
| **Quality** | False fast-track rate | <5% | >10% (kill metric) |
| **Quality** | Per-persona usefulness (board feedback) | >70% | <50% |
| **Efficiency** | Requests resolved without board session | 40%+ | |
| **Efficiency** | Re-assessments using delta mode | >70% | |
| **Adoption** | Architects voluntarily use it | Yes | Mandated = failed |
| **Follow-up** | Conditions tracked in Preflight | >90% | |
| **Follow-up** | Conditions closed on time | >75% | |

---

## Worked Example

→ See [DIGITAL-PATHOLOGY.md](DIGITAL-PATHOLOGY.md) for a complete end-to-end walkthrough: business request through pipeline to board-ready PSA.

---

## Technical Architecture

→ See [ARCHITECTURE.md](ARCHITECTURE.md) for: pipeline implementation details, LLM routing strategy, prompt engineering, embedding pipeline, document parsing, ArchiMate parser scope, deployment architecture, integration architecture, API specification, authentication/authorization design, audit trail schema, testing strategy, and repository structure.

---

## Repository

Source: https://github.com/rvdlaar/preflight

---

*Preflight does the homework. The architect adds judgment. The board makes the call.*
