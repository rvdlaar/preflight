# Prompts v2 — From User Feedback to Better Design

Based on MiroFish panel review of PREFLIGHT.md from the USER perspective (not compliance review).
Each prompt improves the design document based on what the personas said they need as daily users.

---

## Priority 1: Core Hypothesis & First Experience

The product lives or dies on first use. Raven: "Start with one useful thing. Make it indispensable."

| # | Prompt | Why (who said it) |
|---|--------|-------------------|
| 1.1 | "Redesign Phase 1 to minimum viable daily tool. One LLM, one parser, no Milvus. Input: business request + hospital's Archi model. Output: landscape brief (existing apps in this capability space, overlaps, lifecycle status) + draft ZiRA positioning (bedrijfsdomein, bedrijfsfuncties, diensten, processen) + batched persona assessment + 1-page PSA draft. That's it. Prove this is useful before adding anything else." | Raven (start radically smaller), Thomas (portfolio overlap is the killer feature), Marcus (ZiRA positioning is the tedious work), Sophie (bedrijfsfunctie mapping saves 2 days) |
| 1.2 | "Design the first-run experience. New architect, new hospital. They load their Archi model. They paste their first business request. What happens in the next 5 minutes? Walk through every screen, every interaction, every output. This is the moment that makes or breaks adoption." | CIO (voluntary adoption is the metric), Raven (adoption cliff), Marcus (the question is whether output is good enough) |
| 1.3 | "Write the validation protocol. Take 5 real past proposals from the hospital with known board outcomes. Run them through the minimum viable Phase 1. Measure: does the landscape brief find the right overlaps? Does the ZiRA positioning match what the architect wrote? Does the triage match the board's treatment? Define pass/fail criteria and a kill metric (if <3 of 5 match, stop building)." | Raven (validate hypothesis before platform), CIO (retroactive validation on our data) |
| 1.4 | "Design the 'new hospital, day one' experience. An architect joins a new employer. They install Preflight, load the hospital's Archi model and ZiRA, and immediately have a working EA assessment tool that knows the landscape. Design the onboarding flow that makes them look brilliant in their first week." | The evangelism question — this is how it spreads |

---

## Priority 2: The Product That Makes You Look Good

What each persona said would make them champion this.

| # | Prompt | Why (who said it) |
|---|--------|-------------------|
| 2.1 | "Design the PSA draft experience. Marcus opens a request in Preflight and sees a draft PSA with: ZiRA positioning pre-filled, principetoets drafted, domain assessments per persona, risk register populated, open questions identified. He spends 1 hour refining it. The board receives a PSA that would have taken him a week. Show the full PSA template with a worked example for Digital Pathology." | Marcus (70% draft PSA refined in 1 hour = fundamentally changes capacity) |
| 2.2 | "Design the board prep pack experience. CIO opens Preflight Thursday afternoon before the board meeting. Show what they see: number of proposals, estimated board time, traffic lights, one-paragraph summaries, decision options, draft conditions. Per-item view. Post-meeting: decisions recorded, conditions created, zero meeting minutes to write." | CIO (show me the Board Prep Pack working with a real proposal) |
| 2.3 | "Design the portfolio overlap alert. Thomas submits a request for a 'new document management system.' Preflight immediately shows: 3 existing applications in this capability space from ArchiMate, their lifecycle status from the tech radar, the vendor's previous history from assessment history. Show the UI. This is the feature that replaces Thomas's manual LeanIX queries." | Thomas (portfolio overlap detection is Tuesday morning saved) |
| 2.4 | "Design the cascade analysis view. Lena opens a proposal and sees: dependency graph from ArchiMate showing 7 downstream consumers via Cloverleaf, 2 direct database connections (flagged as debt), 1 file-based integration (flagged as debt). Blast radius visualization. This takes her a full day today." | Lena (cascade analysis auto-generated from ArchiMate) |
| 2.5 | "Design the AIVG vendor checklist experience. Nadia opens a vendor-selection assessment and sees: interactive AIVG 2022 + Module ICT checklist, pre-filled where Preflight already has answers from vendor docs, with evidence fields and sign-off for each item. She walks through it with the vendor. This replaces her Excel." | Nadia (interactive checklist replaces Excel, usable in vendor meetings) |
| 2.6 | "Design the clinical impact brief. CMIO opens a proposal and sees a 1-page clinical summary: affected clinical workflows, patient safety assessment, clinical validation requirements, BIV from clinical perspective, integration impact on Cloverleaf/JiveX/Digizorg. Not the full PSA — just the clinical view. Something she can take to the maatschap or vakgroep." | CMIO (clinical summary for medical staff governance, not just EA board) |
| 2.7 | "Design the draft verwerkingsregister entry. FG-DPO opens an assessment that involves personal data. Preflight has auto-generated a draft entry: welke persoonsgegevens, welke betrokkenen, welk doel, welke grondslag, welke bewaartermijn, welke ontvangers. The FG reviews, edits, and signs off. This replaces manual register maintenance." | FG-DPO (verwerkingsregister draft generation = "I would bring this to the FG tomorrow") |
| 2.8 | "Design the STRIDE pre-fill experience. Victor opens an assessment and sees a STRIDE threat model pre-filled with the proposal's actual components: the specific applications, the specific interfaces, the specific data flows — from ArchiMate. Not a generic template. A threat model that already knows the attack surface." | Victor (pre-filled STRIDE = the work nobody does until Victor asks) |
| 2.9 | "Design the vendor intelligence profile. Thomas opens a vendor-selection request and sees the hospital's complete history with this vendor: previous assessments, board decisions, open conditions, AIVG status, NEN 7510 certification, number of systems in landscape, verwerkersovereenkomst status. This is institutional memory that survives architect turnover." | Thomas (vendor knowledge walks out the door when architects leave) |

---

## Priority 3: The Lifecycle (What Makes It THE Tool, Not A Tool)

Preflight isn't useful if it's a side tool. It has to own the lifecycle.

| # | Prompt | Why (who said it) |
|---|--------|-------------------|
| 3.1 | "Design the complete request lifecycle in Preflight. From business submission → architect assignment → preliminary assessment → clarification → architect refinement → board prep pack → board meeting → decision recording → condition creation → condition tracking → resolution → done. Every step happens in Preflight. No email, no Word docs, no Excel trackers. Show the state machine and the UI for each state." | Everyone (the chain breaks if any step goes outside Preflight) |
| 3.2 | "Design the condition lifecycle. Board approves with conditions. Conditions auto-created from persona assessments. Each condition has: owner, due date, evidence field, source persona. Dashboard: what's overdue? What's coming due? Per-assessment: all conditions met = fully cleared. Per-owner: my condition workload. Board view: which assessments still have open conditions?" | Nadia (condition tracking replaces meeting minutes), Marcus (conditions nobody enforces are worse than a clear no) |
| 3.3 | "Design the delta re-assessment workflow. Board says 'go back and address X, Y, Z.' The architect marks what changed. Preflight diffs and re-evaluates only affected personas. Version history with diff view. Board sees: 'v2 addresses conditions 1 and 3 from board's v1 feedback.' This eliminates the iteration loop that makes the current process weeks long." | Marcus (delta re-assessment is the sleeper feature, eliminates the most frustrating part) |
| 3.4 | "Design the institutional memory features. Similar past assessments with match score. Vendor intelligence that accumulates. Architecture debt register linked to ArchiMate. When an architect leaves, their assessment history, vendor knowledge, and debt tracking stay. After 50 assessments, Preflight knows the hospital better than any individual." | Thomas (vendor knowledge), Marcus (debt register), CIO (institutional memory) |
| 3.5 | "Design the architecture debt visualization. Debt heat map on the ArchiMate capability model. Where is debt concentrated? When a new proposal comes in, auto-cross-reference: 'this proposal resolves debt item #47 but creates new debt item #102.' This is strategic portfolio management." | Marcus (architecture debt register = what I maintain in a spreadsheet) |

---

## Priority 4: Document Improvements

What needs to change in PREFLIGHT.md itself based on the user panel.

| # | Prompt | Why (who said it) |
|---|--------|-------------------|
| 4.1 | "Split PREFLIGHT.md into two documents. Document 1: Product Brief (3-5 pages). What it does, who it's for, what the experience looks like for each role, worked example with Digital Pathology, ROI story. This is what the CIO and CMIO read. Document 2: Technical Architecture (current PREFLIGHT.md, restructured). Pipeline design, tech stack, embedding pipeline, deployment. This is what Marcus and the domain architects read." | CIO (my eyes glazed over in the embedding pipeline section), CMIO (this is written for architects not for me), Raven (1800 lines describes a product that doesn't exist yet) |
| 4.2 | "Move the embedding pipeline, Milvus indexing architecture, LLM routing tiers, and document parsing pipeline details to an appendix or separate document. The main document should lead with: what does the user experience, what comes out, what is the workflow. The infrastructure is an implementation detail." | CIO (NemoClaw branding and NVIDIA stack = noise), Sophie (priority inversion — embedding pipeline gets 4 tables, ZiRA positioning gets 6 bullets), Thomas (conference talk architecture) |
| 4.3 | "Add a worked example. Take Digital Pathology from Sysmex end-to-end. Show: the business request as submitted, the intake form responses, the landscape brief generated from ArchiMate, the persona assessments (batched fast mode), the draft PSA with ZiRA positioning, the BIV classification, the triage recommendation. One complete flow. This is worth more than 1800 lines of architecture description." | Marcus (give me the PSA for Digital Pathology), CMIO (run Digital Pathology end-to-end), CIO (one real PSA output is worth more than 1800 lines of description) |
| 4.4 | "Reduce the persona set for the hospital context. The core set is 12-13: CIO, CMIO, Marcus, Sophie, Thomas, Lena, Jan, Aisha, Victor, CISO, ISO-Officer, Nadia, FG-DPO, PO. Erik (Manufacturing/OT) and Petra (R&D) are irrelevant for most hospital proposals. Make them optional extensions, not core personas. The CISO/ISO-Officer can potentially be merged. 17 personas is noise, not signal." | CIO (17 feels heavy, Manufacturing & OT for a hospital?), Raven (what if 12 of 17 produce the same concern rephrased?), Erik (I approve — I'm not relevant for most proposals) |
| 4.5 | "Fix the estimated footprint. '800-1000 lines of Python' is contradicted by the 40+ file repository structure. Be honest about the actual size. This inconsistency was flagged by CIO, Marcus, Thomas, and Raven. It undermines credibility." | CIO, Marcus, Thomas, Raven (all flagged this independently) |
| 4.6 | "Add a realistic Phase 1 timeline. The current 8-week plan for 5 phases is not credible. Show: Phase 1 (2-4 weeks) = minimum viable tool that is already useful. Phase 2 (months 2-3) = integrations and grounding. Phase 3+ = depth features. Each phase delivers standalone value. Include what is explicitly NOT in each phase." | Raven (8-week fantasy), CIO (wildly optimistic or different scope than what ships), Nadia (2-week phase with no auth/audit = compliance gap by design) |
| 4.7 | "Add a section: 'How Architects' Roles Change.' Be honest about the shift from analyst to reviewer/editor. Frame it as amplification not replacement. Address the status threat directly. Name the discomfort. Explain why senior architects benefit most (they spend time on judgment, not grind)." | Raven (adoption cliff, status change drives resistance more than workload) |
| 4.8 | "Add the 'Why not Power Platform?' justification. The current 'No Power Automate. No Copilot Studio.' reads as a manifesto. In a hospital that runs on Microsoft 365, this needs analytical justification, not ideological dismissal. Compare: what Power Platform offers, what it lacks for this use case, why FastAPI + Next.js is the better choice." | Marcus (my CIO will ask), Raven (technical aesthetics driving decisions over user reality) |
| 4.9 | "Add the principetoets methodology. How does Preflight evaluate a proposal against 'Waardevol' or 'Flexibel'? These are qualitative principles. Is the LLM given the principle definition? Does it retrieve hospital-specific interpretations? Sophie says Waardevol (principle 1) should be weighted highest — if a proposal fails Waardevol, nothing else matters." | Marcus (hand-waves how the most judgment-heavy part works), Sophie (Waardevol should be weighted) |
| 4.10 | "Add the Integration Design product template. It currently gets one line. Lena needs: data flow diagram (source, target, middleware), message specs (HL7v2 segments, FHIR resources, field mappings), error handling, volumetrics, SLA, monitoring. Same level of detail as the PSA and BIA templates." | Lena (the product I'd use most is the least specified) |
| 4.11 | "Add explicit human-in-the-loop for FG determination. The FG persona generates a DRAFT assessment that requires the real FG's sign-off before it becomes binding. Add a dedicated approval workflow: 'FG-DPO review required — draft determination pending your confirmation.' This applies to all authority personas (Victor veto, Nadia escalation) but is most critical for FG." | FG-DPO (an LLM cannot make a legal determination on lawfulness of processing) |
| 4.12 | "Add the clinical system triage floor. Any proposal classified as clinical-system cannot be fast-tracked — minimum treatment is standard review with CMIO always active. Add equivalent floors for patient-data (FG-DPO always active) and OT-boundary (Erik always active when detected)." | CMIO (patient safety gap), Erik (OT boundary detection) |
| 4.13 | "Add missing integration: LeanIX. Thomas lives in LeanIX for portfolio management. Application lifecycle statuses, technology risk scores, business criticality ratings are in LeanIX, not Archi. ArchiMate has the architecture view; LeanIX has the portfolio view. Preflight needs both." | Thomas (significant gap — portfolio reasoning without the portfolio tool) |
| 4.14 | "Add the accountability model. When Preflight's assessment is wrong and the board follows it, who is accountable? Make explicit in every output: 'This is a draft assessment generated by AI personas. The architect owns the final assessment. The board owns the decision. Preflight provides analysis, not judgment.'" | Raven (accountability question), FG-DPO (LLM cannot make legal determinations) |

---

## Summary

| Priority | Count | Focus |
|----------|-------|-------|
| 1. Core hypothesis & first experience | 4 | Does it work? Is first use compelling? |
| 2. Features that make you look good | 9 | The specific screens/outputs each persona craves |
| 3. The lifecycle (THE tool, not A tool) | 5 | Own the full request-to-decision lifecycle |
| 4. Document improvements | 14 | Make PREFLIGHT.md itself a better product document |
| **Total** | **32** | |

**Key shift from v1 prompts (46) to v2 (32):** v1 was compliance artifacts (STRIDE, DPIA, NEN 7510 mapping). v2 is product design (what does the user see, what makes them champions). The compliance artifacts are still needed but they're outputs of the tool, not inputs to the design document.

**Execution order:**
1. **1.1 + 1.2** — Redesign Phase 1 and first-run experience
2. **4.1 + 4.3** — Split document + add worked example (Digital Pathology)
3. **2.1 through 2.9** — Design the "makes you look good" experiences
4. **3.1** — Design the full lifecycle
5. Everything else refines and strengthens
