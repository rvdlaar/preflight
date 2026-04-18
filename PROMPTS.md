# Prompts Needed — Design Document to Buildable Specification

Based on MiroFish panel review of PREFLIGHT.md (all 17 personas). Each prompt produces a section or appendix that closes a gap flagged by one or more personas.

---

## A. Preflight Assesses Itself (Dogfooding Artifacts)

These are the artifacts the design document demands from every proposal but does not provide for itself.

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| A1 | "Position Preflight within the ZiRA bedrijfsfunctiemodel. Which bedrijfsdomein does it serve? Which bedrijfsfuncties does it support? Map it through the metamodel: dienst → bedrijfsproces → werkproces → bedrijfsfunctie. Position it in the informatiedomeinenmodel and applicatiefunctiemodel." | Marcus, Sophie | New section: "ZiRA Positioning of Preflight" |
| A2 | "Write a STRIDE threat model for Preflight. Cover all six categories across: the FastAPI service, LLM inference pipeline, document parsing pipeline, Milvus vector store, PostgreSQL audit trail, integrations (TOPdesk, Graph, ArchiMate), the Next.js frontend, and service-to-service authentication." | Victor | Appendix: "STRIDE Threat Model" |
| A3 | "Classify Preflight under the EU AI Act. Is it a high-risk AI system under Annex III? Consider: it influences architectural decisions about medical devices and clinical systems. Provide the classification rationale and compliance obligations." | Aisha, Nadia | Appendix: "EU AI Act Classification" |
| A4 | "Write a DPIA for Preflight under AVG Article 35. Document: all personal data categories processed, betrokkenen, verwerkingsgrondslag per processing activity, doelbinding, dataminimalisatie measures, bewaartermijnen, ontvangers, and risk assessment with mitigations." | FG-DPO, Nadia, PO | Appendix: "DPIA — Preflight" |
| A5 | "Define the verwerkingsgrondslag for each of Preflight's data processing activities. Proposals, vendor documents, ArchiMate model data, TOPdesk CI data, assessment outputs, audit trail entries, Milvus embeddings. Which AVG Article 6 basis applies to each? If bijzondere persoonsgegevens may be present, which Article 9 exception?" | FG-DPO, Nadia | Section in DPIA (A4) |
| A6 | "Perform a BIV classification of Preflight itself. Score Beschikbaarheid, Integriteit, and Vertrouwelijkheid using the same scale defined in the BIA/BIV section. Derive RPO/RTO targets. Identify cascade dependencies." | Jan, Marcus | Appendix: "BIA — Preflight" |
| A7 | "Map Preflight to NEN 7510 controls. For each applicable control in the Statement of Applicability, state: whether it is met by the current design, what implementation is needed, or what gap exists. Focus on: A.6.1, A.9, A.10, A.12.1, A.12.4, A.12.6, A.14.1, A.14.2, A.15." | ISO-Officer, Nadia | Appendix: "NEN 7510 Control Mapping" |
| A8 | "Produce an SBOM (Software Bill of Materials) for Preflight. List every dependency: FastAPI, Milvus, PostgreSQL, NIM, OpenDataLoader-PDF, PyMuPDF, MarkItDown, Unstructured.io, Azure AI Document Intelligence, NeMo Guardrails, Next.js, shadcn/ui, Voyage-3-Large, BGE-M3, Gemini 2.0. For each: license, version policy, CVE scanning approach, and vendor viability assessment. Note OpenDataLoader-PDF's JVM (Java 11+) runtime requirement in the base image." | Victor, Thomas | Appendix: "SBOM & Supply Chain" |
| A9 | "Assess Preflight's own dependencies against AIVG 2022 + Module ICT. For each external provider (Voyage AI, Google Gemini, NVIDIA NIM, Azure AI Document Intelligence): exit-clausule, broncode escrow applicability, data return, 24-month version support, NEN 7510 certification status, verwerkersovereenkomst status, data processing location. Self-hosted open-source components (OpenDataLoader-PDF, PyMuPDF, MarkItDown, Unstructured.io) are documented separately under supply-chain/community-risk." | Thomas, Nadia | Appendix: "AIVG Self-Assessment" |
| A10 | "Assign a technology radar position (ADOPT/TRIAL/ASSESS/HOLD) to every component in Preflight's stack: FastAPI, Milvus, PostgreSQL, NIM, Ollama, OpenDataLoader-PDF, PyMuPDF, MarkItDown, Unstructured.io, Voyage-3-Large, BGE-M3, Gemini 2.0, NeMo Guardrails, Next.js, shadcn/ui, Tailwind." | Thomas | Section: "Technology Radar Assessment" |

---

## B. Architecture & Infrastructure Gaps

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| B1 | "Design the deployment architecture for Preflight. Show where each component runs (GPU compute, standard compute, database, frontend). Include network topology, firewall zones, load balancing, DNS. Cover both on-prem and cloud deployment options. Include a deployment architecture diagram." | Jan | Section: "Deployment Architecture" |
| B2 | "Design the DR plan for Preflight. Define failover for each component: GPU/NIM failure, Milvus unavailability, PostgreSQL failure, frontend failure, integration endpoint unavailability (TOPdesk down, Graph API down). Define degraded mode: what can Preflight still do when subsystems are unavailable?" | Jan, CMIO | Section: "Disaster Recovery & Degraded Mode" |
| B3 | "Design the integration architecture for Preflight. Show how it connects to ArchiMate, TOPdesk, SharePoint, OneDrive, SIEM, and Entra ID. Does it go through the hospital's API gateway or integration layer? Include: integration architecture diagram, error handling per integration, retry/circuit breaker strategy, token management." | Lena | Section: "Integration Architecture" |
| B4 | "Define Preflight's own API surface. Write the OpenAPI specification outline: endpoints, versioning strategy, authentication, rate limiting, error responses. FastAPI generates this — specify what the generated spec must include." | Lena | Section: "API Specification" |
| B5 | "Abstract the embedding and vector store layers. Define an EmbeddingClient protocol and VectorStoreClient protocol analogous to the LLMClient protocol already defined for the LLM router. Show how switching from Milvus to pgvector or from Voyage-3-Large to another model becomes a configuration change, not a code change." | Lena, Thomas | Section: "Embedding & Vector Store Abstraction" |
| B6 | "Design the capacity planning model. How many concurrent assessments can run? What are the resource requirements per assessment (GPU, memory, Milvus queries, PostgreSQL writes)? What happens on board prep day when 10 architects run deep-mode simultaneously?" | Jan | Section: "Capacity Planning" |
| B7 | "Design the encryption strategy. TLS version requirements, certificate management for service-to-service communication, encryption at rest for PostgreSQL and Milvus, key management strategy (which KMS, key rotation)." | Victor | Section: "Encryption Strategy" |
| B8 | "Resolve data residency for all external services. For Gemini 2.0, Voyage AI, Azure AI Document Intelligence: where does data go? If cloud, which region? What data crosses the hospital boundary? Document the decision: self-host, EER-only cloud, or exclude. Note: LlamaParse was excluded at design time on data-residency grounds; replaced by self-hosted OpenDataLoader-PDF." | Aisha, Nadia, FG-DPO | Section: "Data Residency Decisions" |

---

## C. Business Case & Adoption

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| C1 | "Write the TCO analysis for Preflight. Year 1 and year 3. Include: GPU infrastructure (NIM), Milvus hosting, PostgreSQL, LLM API costs per tier, embedding API costs, Azure AI Document Intelligence costs, developer time to build and maintain, security operations cost (pen testing, SIEM rules, vulnerability scanning, access reviews), training." | CIO, Thomas, CISO | Section: "Total Cost of Ownership" |
| C2 | "Write the one-page business case. Current cost per EA assessment (architect hours, board hours, cycle time, delay cost). Projected cost with Preflight. Payback period. Name the business sponsor. Quantify the waardepropositie per ZiRA principle 1." | CIO, Sophie | Section: "Business Case" |
| C3 | "Write the staffing plan. Who builds Preflight? Who maintains it in year two? What skills are needed (Python, LLM engineering, vector databases, Next.js, healthcare domain, security)? Is this one architect's side project or a funded initiative?" | CIO | Section: "Staffing & Ownership" |
| C4 | "Write the organizational change plan. Who drives adoption? What happens to the current intake process during transition? Stakeholder analysis: who benefits, who may resist, what are the mitigation strategies? Include the shadow mode transition plan from parallel running to primary tool." | Sophie | Section: "Organizational Change Plan" |
| C5 | "Write the build-vs-buy analysis. Compare Preflight (build) against: LeanIX, Ardoq, BiZZdesign, ServiceNow EA module, and any other EA assessment tools. What do they offer, what do they lack for this specific use case (persona-driven assessment, ZiRA grounding, Dutch regulatory compliance)?" | Thomas | Section: "Build vs. Buy Analysis" |

---

## D. Prompt Engineering & LLM Quality

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| D1 | "Design the prompt templates for persona simulation. For each persona, define: system prompt structure, how incentives/constraints/domain translate into prompt instructions, output format enforcement, few-shot examples for each rating level (approve/conditional/concern/block). Include the Fast mode (batched PERSPECTIVES) prompt template and the Deep mode (simulatePanel) per-persona prompt template." | Raven (core hypothesis), all personas | Section: "Prompt Engineering Strategy" |
| D2 | "Design the grounding verification strategy. How do you detect when a persona hallucinates a regulatory reference (e.g., cites a NEN 7510 control that does not exist, or an AIVG article that does not exist)? Options: post-generation citation check against the knowledge base, constrained generation, retrieval-augmented citations with source linking." | Raven, CMIO | Section: "Hallucination Mitigation" |
| D3 | "Design the prompt injection mitigation for the document parsing pipeline. Vendor documents and business requests are untrusted input fed through parsers into LLM prompts. How do you prevent a malicious document from influencing persona assessments? Define the NeMo Guardrails configuration." | Victor | Section: "Prompt Injection Defense" |
| D4 | "Design the persona deduplication strategy. When 5 personas all say 'encrypt the data,' how does the output avoid noise? Options: synthesis step that merges overlapping findings, cross-persona deduplication in Step 5, or structured output that separates unique findings from shared consensus." | Raven | Section: "Output Deduplication" |
| D5 | "Design the classification validation strategy. Step 1 classification is a single LLM call that determines the entire downstream pipeline. How do you validate it? Options: confidence scoring with human review below threshold, dual-classification (two calls, compare), rule-based override for known patterns (patient data keywords always trigger CMIO)." | Raven, CMIO, Erik | Section: "Classification Quality Assurance" |

---

## E. Security Operations

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| E1 | "Write the SOC integration plan. Estimated event volume per assessment and per day. SIEM correlation rules for Preflight events. What constitutes a security incident in Preflight? Alert thresholds, response procedures, escalation paths." | CISO, ISO-Officer | Section: "SOC Integration Plan" |
| E2 | "Write the vulnerability management plan for Preflight. Per component: who monitors CVEs, patch SLA (critical/high/medium/low), container image update process for NIM, Python dependency scanning automation, Milvus update process. Named responsibilities." | ISO-Officer | Section: "Vulnerability Management Plan" |
| E3 | "Write the secrets management strategy. How are stored/rotated: LLM API keys, TOPdesk credentials, Microsoft Graph client secrets, Milvus connection credentials, PostgreSQL connection strings. Which secrets manager? Key rotation cadence." | Victor | Section: "Secrets Management" |
| E4 | "Write the risk acceptance memo for LLM usage with sensitive data. Residual risk after NeMo Guardrails, ABAC restrictions, and data classification controls. Present to hospital board for formal risk acceptance decision." | CISO | Appendix: "LLM Risk Acceptance Memo" |
| E5 | "Define the penetration test scope and schedule. What is in scope (FastAPI API, Next.js frontend, LLM prompts, document parsing pipeline, authentication flows)? When is the first test? Re-test cadence? Who conducts it?" | ISO-Officer | Section: "Penetration Test Plan" |

---

## F. Privacy Operations

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| F1 | "Draw the data flow diagram for Preflight. Every processing step from intake to output. Every data store (PostgreSQL, Milvus, parsed document cache, LLM context). Every external service call. Label each node with data classification and identify where personal data exists." | PO, FG-DPO | Diagram: "Preflight Data Flow" |
| F2 | "Design the data subject request workflow. How does a betrokkene exercise inzage, rectificatie, vergetelheid, and dataportabiliteit within Preflight? Specifically address: can personal data be deleted from Milvus vector embeddings? If not, what is the technical mitigation (re-embedding, filtering, pseudonymization)?" | FG-DPO, PO | Section: "Data Subject Request Workflows" |
| F3 | "Design the retention implementation. Per data store (PostgreSQL audit trail, Milvus vectors, parsed markdown, assessment outputs): what is the bewaartermijn? How is deletion automated? How is retention compliance verified?" | PO | Section: "Retention Policy Implementation" |
| F4 | "Draft the verwerkingsregister entry for Preflight per AVG Article 30." | FG-DPO, PO | Appendix: "Verwerkingsregister Entry" |
| F5 | "Design data minimization measures. Can proposals be stripped of identifiable information before LLM inference? Can parsed documents be deleted after embedding? Can the audit trail JSONB details field exclude personal data? What is the minimum personal data Preflight needs to function?" | PO, FG-DPO | Section: "Data Minimization Design" |

---

## G. Domain-Specific Gaps

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| G1 | "Add a clinical system triage floor: any proposal classified as clinical-system cannot be fast-tracked — minimum treatment is standard review with CMIO always active. Document the rationale and update the triage logic." | CMIO | Update to triage logic in PREFLIGHT.md |
| G2 | "Add OT boundary detection as a classification trigger in Step 1. When a proposal touches systems near the IT/OT boundary (network changes, infrastructure changes in production environments), Erik is automatically activated — not just when someone labels it manufacturing-ot." | Erik | Update to classification logic |
| G3 | "Determine whether Preflight itself is a medical device under MDR Article 2. If it produces assessments that influence decisions about clinical systems affecting patient care, does MDR apply? Provide legal reasoning." | CMIO | Appendix: "MDR Self-Assessment" |
| G4 | "Extend the knowledge corpus plan for non-healthcare domains: export control (EAR, ITAR, EU dual-use), PLM integration patterns, IEC 62443 zone/conduit definitions, HPC infrastructure patterns. Define what content is needed and who creates it." | Petra, Erik | Update to Knowledge Base section |
| G5 | "Extend the BIV scoring scale with non-clinical impact descriptions. B=3 for engineering: 'design freeze delayed, product launch missed.' I=3: 'engineering data corrupted, design rework.' V=3: 'IP exfiltrated, export control violation.' Extend data classification to include export-controlled and trade-secret." | Petra | Update to BIV section |
| G6 | "Add an IP Protection Assessment as a ninth architecture product. When a proposal triggers Petra's domain (export control, IP, PLM), what product is generated? Define the template." | Petra | New product template |
| G7 | "Design persona versioning. When persona incentives/constraints are tuned based on feedback (Phase 5), how are versions tracked? How do you reproduce a previous assessment with the exact persona configuration that produced it? Required for MDR traceability." | Marcus, CMIO | Section: "Persona Version Control" |
| G8 | "Define the relationship between Preflight and existing tools. How does Preflight relate to LeanIX (application portfolio)? To TOPdesk GRC module? To the existing ADR register? Are Preflight-generated ADRs draft ADRs entering the existing governance process, or a parallel register?" | Marcus, CIO, Thomas | Section: "Tool Landscape Integration" |

---

## H. Raven's Core Challenge

| # | Prompt | Flagged By | Output |
|---|--------|-----------|--------|
| H1 | "Validate the core hypothesis before building the platform. Design a 1-week experiment: take 5 real past proposals with known board outcomes, run them through a single LLM with the persona prompts, and measure: does the output match what the board decided? Define pass/fail criteria. If <3 of 5 match, the remaining 7 weeks of engineering are wasted." | Raven | Section: "Core Hypothesis Validation Plan" |
| H2 | "Simplify Phase 1 to minimum viable dogfood. Single LLM (no routing), single parser (PyMuPDF or MarkItDown), no Milvus (use pgvector or in-memory), no embedding pipeline, no frontend (CLI or Markdown output). Just: input proposal → classify → select personas → assess (fast mode) → output PSA. Prove value with the simplest possible stack." | Raven, Thomas, Marcus (principle 9) | Update to Phase 1 scope |
| H3 | "Address the accountability question. When Preflight's assessment is wrong and the board follows it, who is accountable? When a DPIA draft misses a critical data flow, is that the architect's failure or the tool's? Document the liability model and make it explicit in every output." | Raven | Section: "Accountability & Liability Model" |

---

## Summary

**Total prompts: 46**

| Category | Count | Priority |
|----------|-------|----------|
| A. Self-assessment (dogfooding artifacts) | 10 | Critical — FG-DPO concern blocks without A4/A5 |
| B. Architecture & infrastructure | 8 | High — Jan, Lena, Victor conditionals |
| C. Business case & adoption | 5 | High — CIO, Sophie conditionals |
| D. Prompt engineering & LLM quality | 5 | Critical — Raven's core hypothesis |
| E. Security operations | 5 | High — CISO, ISO-Officer conditionals |
| F. Privacy operations | 5 | Critical — FG-DPO, PO concerns |
| G. Domain-specific gaps | 8 | Medium — targeted fixes |
| H. Raven's core challenge | 3 | Critical — validates everything else |

**Recommended execution order:**
1. **H1** — Validate core hypothesis (if this fails, everything else is moot)
2. **H2** — Simplify Phase 1 to minimum viable
3. **A4/A5/F1** — DPIA + verwerkingsgrondslag + data flow (FG-DPO blocks without these)
4. **D1** — Prompt engineering (the actual product)
5. **A2/D2/D3** — STRIDE + hallucination + prompt injection (Victor conditionals)
6. **C1/C2** — TCO + business case (CIO conditional)
7. Everything else in parallel
