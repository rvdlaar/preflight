# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Preflight** is an EA intake and pre-assessment tool for a Dutch hospital. It takes a business request and runs it through 22 MiroFish personas (representing the full EA board + security/privacy/compliance officers) to produce board-ready architecture products (PSA, ADR, DPIA, BIA, etc.).

Preflight does **not** replace the EA board — it prepares the board by doing the structured analytical work.

## Document Structure

The design is split across multiple documents:

| Document | Purpose | Audience |
|----------|---------|----------|
| `PREFLIGHT.md` | Product document — what it does, for whom, why, lifecycle | CIO, CMIO, board, architects |
| `ARCHITECTURE.md` | Technical architecture — pipeline, LLM routing, embedding, parsing, auth, audit | Developers, technical architects |
| `DIGITAL-PATHOLOGY.md` | End-to-end worked example (Sysmex) | Everyone — the demo |
| `README.md` | Quick start, CLI commands, project structure, configuration | Developers, new contributors |
| `ZiRA-Reference.md` | ZiRA reference architecture documentation | Domain context |
| `personas/ea-council-personas.mjs` | 20 core + 2 optional MiroFish persona definitions (22 total) | Runtime, prompt engineering |
| `templates/*.md` | 16 Jinja2 output product templates (PSA, ADR, BIA, DPIA, etc.) — bilingual NL/EN | Product generation |
| `src/preflight/` | Python backend — CLI, API, pipeline, LLM, parsing, embedding, auth, synthesis | Implementation |
| `synthesis/*.mjs` | Original JavaScript MiroFish synthesis modules | Reference / porting source |
| `PROMPTS-v2.md` | Backlog of improvement prompts from MiroFish panel review | Development planning |
| `DOCUMENTATION-PLAN.md` | How prompts map to document sections | Development planning |

## Architecture

### Persona-Driven Pipeline (6 steps)

0. **Ingest** — persona-driven discovery queries against ArchiMate/TOPdesk/SharePoint/OneDrive/LeanIX
1. **Classify** — categorize request type + impact level, `selectRelevant()` picks 8-12 personas
2. **Retrieve** — per-persona RAG (not global), scoped by each persona's `domain` keywords
3. **Assess** — Fast mode (batched PERSPECTIVES, single LLM call) or Deep mode (`simulatePanel()`, per-persona calls + interaction rounds)
4. **Challenge** — authority personas act: Security VETO, Risk ESCALATION, FG/DPO DETERMINATION (independent), CMIO PATIENT SAFETY floor, Red Team pre-mortem
5. **Output** — persona-attributed findings → 15 architecture products, bilingual NL/EN

### Key Design Decisions

- **All authority persona outputs are drafts** requiring human confirmation (sign-off workflow in UI)
- **Hard triage floors**: clinical-system cannot be fast-tracked; patient-data always activates FG-DPO
- **20 core personas** + 2 optional extensions (Erik/Manufacturing, Petra/R&D) = 22 total
- **Phase 1 starts simple**: single LLM, pgvector (not Milvus), ArchiMate parser + batched assessment + Markdown PSA output
- **16 output products** (PSA, ADR, Clinical Impact, Process Impact, Vendor, DPIA, BIA/BIV, Integration Design, Network Impact, Security, NFR Spec, EU AI Act, Operational Readiness, Roadmap Impact, Tech Radar, Decommission Checklist)
- **Kill metric**: if false fast-track rate >10% after 3 months shadow mode, stop and reassess

### Tech Stack (planned)

| Layer | Phase 1 | Phase 2+ |
|-------|---------|----------|
| Backend | Python / FastAPI | Same |
| LLM | Single model (Ollama or NIM) | Tiered routing (light/strong/frontier) |
| Vector store | PostgreSQL + pgvector | Milvus (dual collection: dense + sparse) |
| Embedding | Single model | Voyage-3-Large, BGE-M3, Gemini 2.0 (tiered) |
| Document parsing | — | Unstructured.io + LlamaParse + MarkItDown, PyMuPDF |
| Frontend | CLI / Markdown output | Next.js + shadcn/ui + Tailwind |
| Auth | — | Microsoft Entra ID (OIDC) + OAuth 2.1 RBAC/ABAC |
| Audit | — | PostgreSQL (append-only, hash-chained) + SIEM |
| Integrations | ArchiMate parser | + TOPdesk, Graph (SharePoint/OneDrive), LeanIX |

### Reference Architecture

Grounded in **ZiRA** (Ziekenhuis Referentie Architectuur) — Dutch hospital reference architecture by Nictiz. Every assessment maps to ZiRA's 12 principles, bedrijfsfunctiemodel, dienstenmodel, procesmodel, informatiedomeinenmodel, and applicatiefunctiemodel. Tracks the ZiRA → ZaRA transition.

## Domain Context

- Dutch hospital environment — regulatory frameworks: NEN 7510/7512/7513/7516/7517, AVG/GDPR, NIS2, MDR/IVDR, AIVG 2022, Wegiz, EU AI Act
- Hospital systems: Archi (ArchiMate modeling), TOPdesk (CMDB/ITSM/GRC), Cloverleaf (clinical integration engine), JiveX (PACS), Digizorg (external healthcare data exchange), LeanIX (application portfolio)
- Five authority types: Victor VETO, Nadia ESCALATION, FG-DPO INDEPENDENT (cannot be overruled), CMIO PATIENT SAFETY (cannot be fast-tracked), Raven CHALLENGE (advisory)
- NEN 7513 audit logging mandatory for patient-related data access

## Dogfooding Rule

Every significant architecture/design decision for Preflight itself must be assessed by the personas. Assessment output goes in PR description or linked ADR.

## Build Phases

5 phases with realistic timelines: Phase 1 (2-4 weeks, useful on day one), Phase 2 (months 2-3, integrations + grounding), Phase 3 (months 3-4, deep mode + products), Phase 4 (months 4-6, platform + frontend), Phase 5 (ongoing, learning + calibration — non-optional).
