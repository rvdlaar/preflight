# Panel Synthesis v2 — Power User Review

14 architect and business personas reviewed all design docs as daily users.
Question: what makes this the tool they beg new employers to buy?

---

## The Big Insight

Preflight is designed as an **intake/assessment tool** — you submit a request, get a PSA.

But the power users want a **living architecture knowledge platform** that grows with every assessment. The per-assessment output is the entry point. The accumulated intelligence across 50+ assessments is what makes it indispensable and impossible to leave behind.

---

## New Products Requested

| # | Product | Requested By | What It Contains | Why It's Missing Matters |
|---|---------|-------------|-----------------|------------------------|
| 1 | **Process Impact Assessment** | Joris | As-is/to-be BPMN draft, handover analysis, exception paths, process KPI baseline, transition state model | "Preflight has a process architect persona but no process output product" — biggest structural gap |
| 2 | **Network Impact Assessment** | Ruben | Bandwidth per flow, protocol/port requirements, network zone placement, draft firewall rules, QoS, wireless coverage needs | "Every arrow in the integration diagram is network traffic nobody told me about" |
| 3 | **EU AI Act Risk Classification** | Aisha | Risk tier classification (unacceptable/high/limited/minimal), human oversight requirements, transparency obligations, conformity assessment triggers | Clinical AI is almost always high-risk — no product captures this |
| 4 | **Architecture Roadmap Impact** | Femke | Cross-proposal portfolio view: which roadmap items are affected, blocked, or unblocked. Transition architecture for the parallel-run state | "Three proposals this quarter create conflicting transition architectures" |
| 5 | **NFR Specification** | Marco | Auto-generated from BIV scores: availability targets, RPO/RTO, response time stubs, concurrent user stubs, retention periods from FG assessment | "The project team needs NFRs. Nobody writes them." |
| 6 | **Operational Readiness Checklist** | Jan | Monitoring setup, alerting rules, backup schedule, patching procedure, escalation path, on-call assignment | "Every new system needs this. Nobody produces it until go-live." |

## Features Needing More Depth

| # | Feature | Requested By | What's Missing |
|---|---------|-------------|---------------|
| 1 | **Clinical Impact Brief** | CMIO | Must be in clinical language for maatschap/vakgroep, not architecture language. Clinical pathway change visualization. Medication circuit awareness (G-Standaard, KNMP). |
| 2 | **Integration Design** | Lena | Cloverleaf route configuration awareness (not just conceptual). Message profile analysis (HL7v2 segments, Z-segments, FHIR profiles). Interface contract registry (designed vs. actually implemented). |
| 3 | **Architecture Debt Register** | Femke, Marcus | Heat map on capability model. Debt trading (proposals creating AND resolving debt). Principle violation trends over time. |
| 4 | **Condition Tracking** | CIO, Marcus | Escalation when overdue. Automated reminders. Lifecycle reporting: "Of 47 conditions in Q1, 31 closed, 8 overdue — most common overdue type: verwerkersovereenkomst." |
| 5 | **AIVG Checklist** | Thomas, Nadia | Interactive workflow — update status in real-time with vendor. Vendor-facing view for them to fill in. Evidence attachment. Compliance report generation. |
| 6 | **Verwerkersovereenkomst** | Nadia | Full lifecycle: signed date, expiry, sub-processor list, BOZ conformity, last review date. She tracks 47 in a spreadsheet. |
| 7 | **Principetoets** | Marcus, Sophie | Algorithmic where possible (Eenvoudig: compare pre/post component count from ArchiMate). Waardevol weighted primary. |
| 8 | **Decommission Assessment** | Thomas | Equal depth to acquisition assessment: data migration, interface sunset sequencing, user transition, cascade impact of removal. |
| 9 | **Data Classification** | Aisha | Structured and consistent methodology, not LLM interpretation. Aligned with BIV V dimension and AVG categories. |

## Persistent Features (Not Per-Assessment — Always-On)

The recurring theme: power users want features that live beyond individual assessments.

| # | Feature | Requested By | What It Does |
|---|---------|-------------|-------------|
| 1 | **Cascade dependency graph** | Lena, Jan | `preflight cascade --system "Labosys"` — instant blast radius for ANY system, always current from ArchiMate. Not just for new proposals. For DR planning, patching coordination, incident response. |
| 2 | **Information ownership registry** | Daan | Persistent registry: "Medicatieoverzicht — authoritative source: EPD, owner: Apotheek, consumers: 7 systems." Every assessment checks against this. |
| 3 | **Verwerkingsregister** | Nadia, Aisha, FG-DPO | Cumulative register from all assessment DPIA drafts. Queryable. AP audit-ready within 24 hours. |
| 4 | **Solution pattern library** | Marco | "Show me all solutions that used Cloverleaf for DICOM routing" — which worked, which failed, why. Pattern reuse across assessments. |
| 5 | **Standards compliance aggregate** | Femke, Marcus | After 50 assessments: "ZiRA principle 9 violated in 60% of proposals. Portfolio is getting more complex, not simpler." Architecture culture metrics. |
| 6 | **Architecture KPIs** | Femke | % landscape aligned with target architecture, debt trend, standards compliance rate, roadmap delivery rate. Computed from assessment history. |
| 7 | **DR tier distribution** | Jan | How many Tier 1/2/3 systems do we have? Can DR infrastructure handle another B=3 system? |
| 8 | **Cross-assessment impact** | Marcus | "Assessment #42 and #45 compete for the same capability space. Board should review together." |
| 9 | **Vendor contract lifecycle** | Thomas, Nadia | Expiry dates, auto-renewal status, exit clause exercise windows. Integrated into assessment context. |

## New Integrations Requested

| Integration | Requested By | What It Adds |
|-------------|-------------|-------------|
| **LeanIX bidirectional** | Thomas | Write back: create fact sheet draft, set lifecycle, link capability when board approves |
| **Cloverleaf route config** | Lena | Query existing routes, transforms, sites. Estimate effort for new routes. |
| **Process mining (Celonis)** | Joris | As-is process reality (not just documentation). Bottleneck data, conformance checking. |
| **Financial/budget systems** | CIO | Budget envelope tracking, investment portfolio link, TCO against actual spend |
| **Network monitoring** | Ruben | Current link utilization to overlay capacity impact assessments |

## Executive Dashboard (Shared Demand)

CIO, CMIO, and Nadia all said: **CLI-only won't get executive buy-in. Need a read-only dashboard by Phase 2, not Phase 4.**

Must show:
- Pipeline status: how many requests in each state
- Board agenda: upcoming items with traffic lights
- Condition status: what's overdue, what's approaching, who's stuck
- Architecture KPIs: debt trend, compliance rate, triage distribution
- Besluitenlijst: structured decision list from board meetings

## Killer Feature Per Persona

| Persona | "I never go back if this works" |
|---------|-------------------------------|
| Sophie | ZiRA positioning auto-fill in PSA |
| Joris | Process-aware assessments that identify handovers and exceptions automatically |
| Marcus | Parallel persona assessment replacing sequential weeks of meetings |
| Thomas | Portfolio overlap detection from ArchiMate in seconds |
| Lena | Auto-generated cascade dependency diagrams from ArchiMate |
| Daan | Automatic cross-reference between hospital data objects and ZiRA informatieobjecten/zibs |
| Marco | Conditions as structured, dependency-linked requirements with lifecycle |
| Jan | Cascade dependency diagram for any system, always current (not just new proposals) |
| Ruben | Auto-generated network zone placement and firewall rules from integration architecture |
| Aisha | Data flow diagram with classification labels for DPIA, auto-generated |
| Femke | Cumulative architecture debt register linked to ArchiMate, computed from all assessments |
| CIO | Killing the iteration loop — 13 personas ask the board's questions before the board meets |
| CMIO | Proactive instead of reactive — clinical impact assessed before anyone walks into the board room |
| Nadia | Compliance as starting point instead of afterthought — regulatory matrix generated in Step 1 |

## What Everyone Agrees On

1. **30-day pilot with real proposals** is the minimum threshold before budget commitment
2. **The output quality IS the product** — templates, diagrams, bilingual formatting matter more than UI
3. **Institutional memory is the long-term moat** — after 50 assessments, Preflight knows the hospital better than any individual
4. **One wrong fact kills trust permanently** — especially clinical (CMIO) and regulatory (Nadia)
5. **The tool must grow with use** — assessment 50 must be dramatically better than assessment 1

## What Divides Them

- **Process artifact gap**: Joris says this is the biggest structural gap. Other personas did not notice because they don't think in processes.
- **Network assessment gap**: Ruben says he's in the persona table but absent from the worked example. He's right — the Digital Pathology example skips network entirely.
- **Depth vs. breadth trade-off**: Femke and Daan want deep portfolio/information architecture features. Marco wants solution delivery features. Both are valid but pull in different directions.
- **CLI vs. dashboard timing**: Architects are fine with CLI in Phase 1. Executives need a dashboard by Phase 2.
