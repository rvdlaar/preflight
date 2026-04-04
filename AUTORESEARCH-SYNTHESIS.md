# Autoresearch Synthesis — What This Means for Preflight

*April 2026. Based on: competitive analysis, EA pain point research, and Dutch healthcare EA landscape study.*

---

## The One-Line Positioning

**Preflight is not an EA tool. It's the front door that every EA tool is missing.**

Every competitor manages the portfolio after decisions are made. None handles the intake-to-decision pipeline. Preflight creates a new category: AI-powered EA intake and pre-assessment.

---

## Five Validated Bets

### 1. The Intake Void Is Real and Universal

No commercial EA tool handles the process between "business says we want X" and "board decides." Not LeanIX, not Ardoq, not BiZZdesign, not ServiceNow, not MEGA. This gap is confirmed by:
- EA practitioners: cycle time of weeks to months is the #1 complaint
- Tool vendors: none even claims to solve intake
- ADOIT 18.0's Structured Approvals is the closest — but it handles approval of existing artifacts, not assessment of new proposals

**Implication**: Preflight is genuinely novel. Don't position against existing tools. Position as the missing piece.

### 2. "Time to First PSA" Is the Killer Metric

Every pain point traces to cycle time. The research shows:
- 2-6 weeks typical cycle in Dutch hospitals (ARB meeting monthly)
- Two weeks of documentation prep per significant decision
- DevOps teams view ARBs as "speed bumps"

If Preflight delivers a draft PSA in minutes, that's not incremental — it's a category shift. This must be demonstrable in a 5-minute demo.

**Implication**: The first-run experience in FIRST-RUN.md is the entire product strategy. If the demo doesn't wow, nothing else matters.

### 3. The Output IS the Distribution

Figma grew to 285,000 DAUs in year one with zero marketing. Every shared Figma prototype introduced the tool to non-users. The same pattern applies:
- The PSA gets shared with board members (who don't use Preflight)
- The board prep pack gets shared with the CIO
- The AIVG checklist gets walked through with vendors
- The DPIA draft gets shared with the FG

Every shared document is an ad for Preflight. The output quality is the marketing budget.

**Implication**: Product investment should go into output quality (templates, diagrams, bilingual formatting) more than into the UI. The Markdown output IS the product for most stakeholders.

### 4. Don't Be a Repository (Repositories Rot)

66% of EA projects fail. 18% of practitioners say their EA data is unreliable. The pattern:
1. Tool gets implemented with consulting help
2. Data is current for 6 months
3. Maintenance is deprioritized
4. Nobody trusts the data
5. Tool becomes shelfware

Preflight avoids this because it's a lens, not a warehouse. It queries Archi, TOPdesk, LeanIX, SharePoint — the systems that are already maintained. It doesn't create a new repository to rot.

**Implication**: Never store master data. Always query the source system. The `--watch` folder feature and live integrations are not convenience features — they're survival features.

### 5. The Dutch Healthcare Market Is Small, High-Leverage, and Unserved

- ~70 general hospitals + 7 UMCs = ~77 potential customers
- ~100-200 practicing hospital architects nationally
- Word-of-mouth is the distribution channel (everyone knows everyone)
- ZiRA is universal but no tool supports it natively
- NEN 7510/AIVG/Wegiz/NIS2 compliance is consuming architect capacity
- Formal intake processes are rare — most run on email and hallway conversations

**Implication**: One successful deployment → demo at Zorg & ICT conference → 10 hospitals interested within 6 months. The market is small enough for direct sales and large enough to build a sustainable business.

---

## Three Risks the Research Surfaced

### Risk 1: Ardoq Moves First

Ardoq has the most mature AI stack (model routing engine, AI Chat, AI Lens). If any incumbent extends into proposal assessment, it's them. They don't have it today, but they have the infrastructure to build it.

**Mitigation**: Time-to-market. Preflight's healthcare specificity (ZiRA, NEN, AIVG) is a moat Ardoq won't build for 77 hospitals. Ship Phase 1, get 3 hospitals using it, and the domain knowledge becomes the defensible advantage.

### Risk 2: The 70% Output Trap

The research warns that AI-generated documents in the "uncanny valley" (good enough to rely on, not good enough to be right) are the most dangerous outcome. Architects rubber-stamp comprehensive-looking output.

**Mitigation**: Already addressed — accountability model, human-in-the-loop for authority determinations, explicit "draft" labeling. But the research says this needs to be more than a disclaimer. The output should have **visible gaps** that force the architect to engage: "[ARCHITECT INPUT NEEDED: which pathologists were consulted about adoption?]" — not just a generic "this is a draft."

### Risk 3: The Knowledge Base Bootstrap

The research confirms: manual knowledge base maintenance kills EA tools. Preflight's ingestion feature (`preflight ingest <folder>`) addresses this, but the regulatory knowledge base (NEN 7510, AIVG, ZiRA) needs to ship pre-built. If the architect has to create the regulatory corpus before getting value, it's the six-month implementation death spiral.

**Mitigation**: Ship Phase 1 with built-in regulatory knowledge. ZiRA models, NEN standards, AIVG clauses — embedded in the distribution, not a setup step. The architect adds hospital-specific knowledge incrementally, but the regulatory baseline is day-one.

---

## What to Change in the Design

Based on this research, three changes to the current design:

### 1. Add "[ARCHITECT INPUT NEEDED]" Markers

When a persona assessment is generic because landscape context is missing, or when a finding requires human validation, the output should explicitly call it out:

```
### CMIO: CONDITIONAL
Clinical validation studies required for diagnostic equivalence.

[ARCHITECT INPUT NEEDED: Has the pathology department been consulted?
How many pathologists support this transition? Which tissue types
are in scope for the initial deployment?]
```

This prevents rubber-stamping and forces engagement with the output.

### 2. Ship Regulatory Knowledge Built-In

Phase 1 must include pre-built knowledge chunks for:
- ZiRA v1.4 (bedrijfsfunctiemodel, informatiedomeinenmodel, procesmodel, principes)
- NEN 7510 controls (mapped to typical assessment scenarios)
- AIVG 2022 + Module ICT (checklist items with guidance)
- AVG/GDPR (verwerkingsgrondslagen, DPIA triggers, rechten betrokkenen)
- NIS2 (essential entity requirements for healthcare)

This is not a nice-to-have. Without it, Nadia and Victor reason from LLM training data, which means hallucinated control numbers and fabricated article references.

### 3. Position as Complementary, Not Competitive

The go-to-market message is: "Preflight makes your existing tools useful."
- Already use Archi? → Preflight queries it automatically
- Already use LeanIX? → Preflight enriches with portfolio data
- Already use TOPdesk? → Preflight pulls CMDB context
- Already use BiZZdesign? → Preflight parses your models

Don't ask hospitals to switch tools. Ask them to point Preflight at what they already have.

---

## Sources

See:
- [COMPETITIVE-ANALYSIS.md](COMPETITIVE-ANALYSIS.md) — full tool-by-tool competitive analysis with comparison table
- EA Pain Point Research (agent output, April 2026) — practitioner forums, analyst reports, adoption studies
- Dutch Healthcare EA Research (agent output, April 2026) — ZiRA community, ZaRA transition, hospital tooling landscape
