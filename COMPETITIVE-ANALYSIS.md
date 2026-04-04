# Preflight Competitive Analysis

*April 2026*

---

## Comparison Table

| Capability | Preflight | LeanIX | Ardoq | BiZZdesign | ServiceNow | Sparx EA | MEGA HOPEX | Avolution ABACUS | Orbus iServer | BOC ADOIT |
|---|---|---|---|---|---|---|---|---|---|---|
| **Core strength** | AI intake + pre-assessment | App portfolio mgmt | Metamodel + AI Lens | ArchiMate modeling + GRC | CMDB + ITSM integration | UML/ArchiMate modeling | EA + GRC governance | Roadmapping + analysis | MS integration + transformation | EA mgmt + structured approvals |
| **AI/LLM features** | Multi-persona LLM assessment pipeline | AI for documentation, research | AI Chat, AI Lens, model routing engine | AI-assisted design (limited) | AI inventory modeling, AI Control Tower | AI-assisted queries, diagram summaries | GenAI for discovery, smart recommendations | Limited / not prominent | 22 AI features (OrbusInfinity) | MCP AI reasoning (v18.0) |
| **Intake workflow** | Full lifecycle: submit -> assess -> board -> conditions -> close | No dedicated intake | ShiftX workflow (process, not EA intake) | No dedicated intake | Data Certification workflows (not intake) | None | No dedicated intake | None | Workflow automation | Structured Approvals (v18.0) — closest, but approval-only |
| **Multi-perspective assessment** | 19 named personas with domain expertise, authority model, interaction rounds | No | No | No | No | No | No | No | No | No |
| **Dutch healthcare (ZiRA/NEN/AIVG)** | Native: ZiRA grounding, NEN 7510/7512/7513, AIVG 2022, BIV classification | No | No | ArchiMate + TOGAF (no ZiRA) | No | Used by Nictiz for ZiRA modeling (tool only) | No | No | No | No |
| **ArchiMate model parsing** | Custom XML parser with relationship traversal | No (separate tool) | Import/API | Native modeling | CMDB (not ArchiMate) | Native modeling | Native modeling | Native modeling | Native modeling | Native modeling |
| **Pricing model** | Self-hosted, per-assessment marginal cost | SaaS subscription (custom quote) | Per-application managed | SaaS subscription | Per-user platform licensing | Perpetual: $245-$750/license | Tiered SaaS (Baseline/Smart/Premium) | Tiered (Foundation/Advanced/Enterprise) | ~GBP 12k/feature + enterprise | Free community edition; enterprise custom |
| **Assessment output** | Draft PSA, ADR, DPIA, BIA/BIV, STRIDE, vendor assessment, integration design — all bilingual NL/EN | Dashboards, reports | Dashboards, scenarios | Models, views, reports | Dashboards, CMDB views | Models, documents | Dashboards, compliance reports | Roadmaps, capability maps | Models, process maps | Models, dashboards |
| **Board preparation** | Agenda with estimated time, risk flags, decision options, post-meeting condition tracking | No | No | No | No | No | No | No | No | No |
| **Condition tracking** | Built-in: owner, due date, evidence, dashboard | No | No | No | Possible via ITSM tasks | No | GRC can track | No | GRC module | Structured Approvals (partial) |

---

## Per-Tool Analysis

### 1. SAP LeanIX

**Core strength:** Application Portfolio Management. Best-in-class for understanding what you have, lifecycle status, technology risk, business criticality. Strong TCO and rationalization capabilities.

**What it does NOT do:** LeanIX manages the portfolio — it does not assess incoming requests against that portfolio. There is no intake workflow, no multi-perspective assessment, no board preparation. AI features focus on automating documentation and data entry, not evaluating proposals. No Dutch healthcare specifics.

**Gap Preflight fills:** Preflight is the front door that LeanIX lacks. Preflight can consume LeanIX data (planned Phase 2 integration) to enrich assessments with portfolio context, but LeanIX cannot do what Preflight does: take a raw business request and produce a board-ready assessment.

**Pricing:** Custom SaaS subscription, reportedly EUR 40-80k+/year for mid-size organizations.

### 2. Ardoq

**Core strength:** Most AI-forward of the incumbents. AI Lens for AI governance, AI Chat for natural language queries, model routing engine that selects optimal LLM per task. Metamodel-driven, flexible data model.

**What it does NOT do:** Ardoq's AI assists with exploring and governing the existing landscape — it does not simulate multi-perspective assessment of new proposals. ShiftX handles process workflows, not EA intake. AI Lens governs AI usage across the enterprise, not architecture decision-making. No healthcare-specific content.

**Gap Preflight fills:** Ardoq is the closest competitor in AI maturity, but its AI answers questions about what exists. Preflight answers "should we do this?" from multiple expert perspectives before it exists. Different problem entirely.

**Pricing:** Per-application managed (not per-user). Custom quote.

### 3. BiZZdesign HoriZZon

**Core strength:** 2025 Gartner MQ Leader with highest average score across all use cases. Deep ArchiMate modeling, integrated EA + SPM + GRC. Strong in regulated industries.

**What it does NOT do:** BiZZdesign is a modeling and governance platform, not an assessment engine. AI features are limited — users actively request more AI. No intake workflow. No automated assessment. No Dutch healthcare specifics despite being a Dutch company.

**Gap Preflight fills:** BiZZdesign models the architecture. Preflight assesses changes to that architecture. They are complementary — Preflight could consume BiZZdesign models the same way it consumes Archi models.

**Pricing:** SaaS subscription, custom quote. Enterprise-grade pricing.

### 4. ServiceNow

**Core strength:** The platform advantage. EA module sits on top of CMDB, connects to ITSM, ITOM, GRC. Zurich release (2026) adds AI agents, application health scoring, AI Control Tower integration. Strongest where EA governance needs to connect to operational IT.

**What it does NOT do:** ServiceNow EA is portfolio visualization and governance on top of CMDB data. It does not assess proposals. AI features focus on inventory modeling and compliance dashboards, not evaluating whether a new system should be acquired. Data Certification is about keeping records current, not intake assessment. No healthcare EA specifics.

**Gap Preflight fills:** ServiceNow knows what you operate. Preflight evaluates what you should acquire. ServiceNow could be an integration target (like TOPdesk) rather than a competitor.

**Pricing:** Enterprise platform licensing. Typically EUR 100k+/year for EA module as part of broader ServiceNow deployment.

### 5. Sparx Systems Enterprise Architect

**Core strength:** Most affordable modeling tool. Perpetual license model. Deep UML/ArchiMate/BPMN support. Notably, Nictiz used Sparx EA to build the ZiRA model itself.

**What it does NOT do:** Sparx EA is a modeling tool, full stop. AI features are basic (query assistance, diagram summaries). No workflow, no governance, no assessment, no intake. It creates the models that Preflight would consume.

**Gap Preflight fills:** Total. Sparx EA creates ArchiMate models. Preflight parses and reasons over them. Zero overlap.

**Pricing:** $245-$750 perpetual license per seat. Most affordable option.

### 6. MEGA HOPEX

**Core strength:** 11 consecutive years as Gartner MQ Leader. Strongest in combined EA + GRC. V5 adds automatic discovery, AI-driven capability mapping, smart recommendations. New data governance module.

**What it does NOT do:** HOPEX governance is about maintaining and rationalizing what exists. AI features assist with discovery and recommendations, not multi-perspective proposal assessment. No intake workflow for new requests. No healthcare-specific frameworks.

**Gap Preflight fills:** HOPEX can tell you your current state is messy. Preflight can tell you whether a proposed change will make it messier or cleaner, from 19 expert perspectives, before you commit.

**Pricing:** Tiered SaaS (Baseline/Smart/Premium). Enterprise pricing, custom quote.

### 7. Avolution ABACUS

**Core strength:** Best-in-class roadmapping and simulation. Customizable metamodel, analytical engines, 3D modeling. Solution Accelerators for common EA patterns.

**What it does NOT do:** ABACUS is planning and analysis of the existing and future landscape. No intake workflow. AI features are not prominent in their marketing. No assessment pipeline. No healthcare specifics.

**Gap Preflight fills:** ABACUS plans the roadmap. Preflight assesses whether a specific proposal belongs on that roadmap.

**Pricing:** Tiered (Foundation/Advanced/Enterprise). Custom quote.

### 8. Orbus Software (OrbusInfinity)

**Core strength:** Microsoft ecosystem integration. 22 AI-driven features (Forrester-recognized). Transitioning from iServer to cloud-native OrbusInfinity platform. Strong in business process analysis.

**What it does NOT do:** Despite having 22 AI features, these focus on modeling assistance and connectivity, not proposal assessment. Workflow automation exists but is process-focused, not EA intake. No healthcare specifics.

**Gap Preflight fills:** OrbusInfinity connects to 150+ business apps. Preflight connects business requests to architecture decisions. Different connectivity.

**Pricing:** ~GBP 12,000/feature for Standard. Enterprise custom quote. Note: iServer end-of-life in progress — migration to OrbusInfinity required.

### 9. BOC ADOIT

**Core strength:** ADOIT 18.0 (Nov 2025) is the most interesting recent release in this space. MCP AI reasoning, transitive search across layers, and Structured Approvals. Free community edition lowers barrier to entry.

**What it does NOT do:** Structured Approvals is the closest any competitor gets to intake governance — but it is approval of existing architecture artifacts, not automated assessment of new proposals. MCP AI reasoning answers questions about the repository, not "should we do this?" No healthcare specifics.

**Gap Preflight fills:** ADOIT 18.0's Structured Approvals could handle the tail end of Preflight's workflow (board approval recording). But everything upstream — intake, classification, multi-perspective assessment, challenge chain, draft architecture products — does not exist in ADOIT.

**Pricing:** Free community edition. Enterprise pricing custom.

---

## Emerging Landscape

### AI-Powered EA Assessment (new entrants)

**ArchHypo.AI** (2026, academic): LLM-based tool for managing architecture uncertainty with hypothesis engineering. Closest in concept to Preflight's approach but focused on agile software architecture, not enterprise architecture governance. No healthcare focus.

**Forrester's "Augmented Architect" concept** (2025): Describes the future where AI agents provide comprehensive, grounded feedback on architecture patterns using RAG and vector databases. This is exactly what Preflight implements — Forrester validates the direction but no commercial product delivers it yet.

**Academic research** (2025-2026): Multiple papers on LLM-based quality assessment of architecture diagrams and generative AI for software architecting. Confirms the field is emerging but no production tools exist.

### Healthcare EA Tools

**No dedicated healthcare EA tool exists.** ZiRA itself is a reference architecture (content), not a tool. It was modeled in Sparx EA. Hospitals use general-purpose EA tools (often BiZZdesign or Sparx EA in the Netherlands) and manually apply ZiRA.

The Open Group's O-VBA (Value-Based Architecture for Healthcare) is a framework, not a tool. No vendor has productized healthcare-specific EA assessment.

### Multi-Perspective / Persona-Driven Assessment

**No commercial EA tool uses persona-driven assessment.** The AI Cabinet Method and DigitalEgo are research concepts for multi-perspective AI deliberation. PersonaGenius AI applies personas to software testing, not architecture. The approach is validated in academic literature but Preflight would be the first to apply it to EA governance.

---

## Strategic Gaps Preflight Exploits

### Gap 1: The Intake Void
Every tool manages the portfolio after decisions are made. None handles the process of evaluating a proposal before the decision. The space between "business says we want X" and "board decides" is manual everywhere.

### Gap 2: Assessment, Not Just Visualization
All competitors answer "what do we have?" Preflight answers "should we do this?" These are fundamentally different questions. No competitor uses AI to generate a multi-perspective assessment of a proposal.

### Gap 3: Healthcare Specificity
Zero competitors support ZiRA, NEN 7510/7512/7513, AIVG 2022, BIV classification, or Dutch regulatory requirements natively. Every Dutch hospital using these tools is manually bridging between the tool and their regulatory context.

### Gap 4: Board Preparation
No tool generates board-ready packages with estimated discussion time, decision options, pre-filled conditions, and post-meeting decision recording. Board preparation is manual document assembly everywhere.

### Gap 5: Persona-Driven Multi-Perspective Reasoning
No tool simulates multiple expert perspectives evaluating a proposal. The closest is ADOIT's Structured Approvals (human reviewers approve artifacts) and Ardoq's AI Chat (single-perspective Q&A on existing data).

### Gap 6: Architecture Product Generation
No tool generates draft PSAs, DPIAs, STRIDE analyses, or vendor assessments from a business request. All tools expect architects to create these documents manually using the tool's modeling and visualization features.

---

## Positioning Summary

Preflight is not competing with EA modeling tools. It is creating a new category: **AI-powered EA intake and pre-assessment**. The competitive moat is:

1. **Persona-driven assessment** — no competitor has this
2. **Healthcare-native** — ZiRA/NEN/AIVG grounding that no competitor offers
3. **Full intake lifecycle** — from business request to board decision to condition closure
4. **Architecture product generation** — draft documents, not just dashboards
5. **Complementary, not competitive** — integrates with LeanIX, consumes Archi/BiZZdesign models, could feed ServiceNow

The risk is not that a competitor builds this. The risk is that Ardoq or MEGA extend their AI capabilities to include proposal assessment. Ardoq's model routing engine and AI maturity make them the most likely to move in this direction. Time-to-market matters.

---

## Sources

- [SAP LeanIX AI Capabilities](https://help.sap.com/docs/leanix/ea/ai-capabilities)
- [SAP LeanIX EA Insights 2025](https://www.leanix.net/en/company/press/sap-leanix-ea-insights-2025)
- [Ardoq Q1 2026 AI Roundup](https://www.ardoq.com/blog/q1-2026-ardoq-ai-roundup)
- [Ardoq 2025 in Review: Connected Intelligence](https://www.ardoq.com/blog/ardoq-2025-connected-intelligence)
- [Ardoq AI Lens and Governance](https://www.ardoq.com/blog/q3-2025-ardoq-ai-roundup)
- [BiZZdesign HoriZZon Platform](https://bizzdesign.com/transformation-suite/horizzon)
- [BiZZdesign Gartner Reviews 2026](https://www.gartner.com/reviews/market/enterprise-architecture-tools/vendor/bizzdesign/product/horizzon)
- [ServiceNow Q4 2025 EA Release](https://www.servicenow.com/community/enterprise-architecture-blog/q4-2025-store-release-empower-enterprise-architects-with-ai/ba-p/3447031)
- [ServiceNow Zurich EA Workspace](https://www.servicenow.com/community/enterprise-architecture-blog/zurich-enterprise-architecture-workspace-monitor-and-use-ai/ba-p/3332510)
- [Sparx EA Pricing](https://sparxsystems.com/products/ea/shop/)
- [Nictiz ZiRA in Sparx EA](https://www.sparxsystems.eu/applications/enterprise-architecture-management-eam/nictiz/)
- [MEGA HOPEX V5 Platform](https://store.mega.com/bundles/details/e8c0d992-ddc9-4904-ae47-a13e70b37c95)
- [MEGA HOPEX Features](https://www.mega.com/features/hopex-platform)
- [Avolution ABACUS Platform](https://www.avolutionsoftware.com/abacus/)
- [Orbus OrbusInfinity Platform](https://www.orbussoftware.com/)
- [Orbus iServer Migration](https://www.orbussoftware.com/customers/iserver-migration)
- [ADOIT 18.0 Release](https://www.prnewswire.com/news-releases/adoit-18-0-redefining-enterprise-architecture-with-built-in-intelligence-302607703.html)
- [BOC Group EA Trends 2026](https://www.boc-group.com/en/blog/ea/ea-outlook-trends-2025/)
- [Forrester: The Augmented Architect](https://www.forrester.com/blogs/the-augmented-architect-real-time-enterprise-architecture-in-the-age-of-ai/)
- [ArchHypo.AI (Springer)](https://link.springer.com/chapter/10.1007/978-3-032-22375-3_12)
- [ZiRA: Dutch Hospital Reference Architecture (Open Group)](https://blog.opengroup.org/2022/06/23/zira-the-dutch-hospital-reference-architecture-a-tool-to-address-a-worldwide-need/)
- [ZiRA in SpringerLink](https://link.springer.com/chapter/10.1007/978-3-031-80704-6_9)
- [O-VBA Healthcare Architecture (Open Group)](https://blog.opengroup.org/2024/04/17/the-o-vba-value-based-architecture-for-healthcare-part-1/)
- [Ardoq Knowledge Graphs to Digital Twins](https://www.infotech.com/software-reviews/research/knowledge-graphs-to-digital-twins-ardoq-s-vision-for-ai-in-enterprise-architecture)
