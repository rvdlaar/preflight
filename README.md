# Preflight

EA intake and pre-assessment tool for Dutch hospitals.

Takes a business request, runs it through 22 MiroFish personas (EA board + security/privacy/compliance officers), and produces board-ready architecture products (PSA, ADR, DPIA, BIA, etc.).

**Preflight does not replace the EA board — it prepares the board by doing the structured analytical work.**

## Quick Start

```bash
# Set up environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the quick scanner (no LLM needed)
python preflight quick-scan "We want to implement Digital Pathology from Sysmex"

# Run full assessment (requires Ollama)
python preflight full-assess "We need a new VPN for remote workers" --heuristic-classify

# Seed the database
python scripts/seed.py

# Run tests
python -m pytest src/tests/ -q

# Start API server
uvicorn preflight.api.app:app --reload
```

## Docker

```bash
# Start PostgreSQL (pgvector) + Ollama
docker compose up -d

# Run migrations
alembic upgrade head

# Seed sample data
python scripts/seed.py
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `preflight quick-scan <request>` | 30-second heuristic classification (no LLM) |
| `preflight full-assess <request>` | Full pipeline: classify → assess → synthesize |
| `preflight assess <request>` | Direct LLM assessment (deprecated, use full-assess) |
| `preflight ingest <path>` | Parse + chunk + embed a document into the knowledge base |

### Key Flags

- `--heuristic-classify` — Use heuristic classification (no LLM call, fast)
- `--mode deep` — Per-persona assessment with interaction rounds
- `--language nl` — Output language (nl/en, default: nl)
- `--store-url` — PostgreSQL URL for pgvector retrieval
- `--reranker` — Enable cross-encoder reranking
- `--hyde` — Enable HyDE (Hypothetical Document Embeddings) for retrieval

## Architecture

```
Request → Classify → Select Personas → Retrieve (RAG) → Assess → Challenge → Output
   │          │              │                │            │         │        │
   │      Heuristic     Triage floors    Per-persona   Authority  Red team  15+ documents
   │      or LLM        & floors         alpha blend    actions   pre-mortem  (PSA, ADR,
   │                                                                     DPIA, BIA, ...)
   │
   └── Guard hooks: BSN detection, injection detection, NEN 7513 audit
```

### 22 Personas (20 core + 2 optional)

CIO, CMIO, Chief Architect, Business, Process, Application, Integration, Infrastructure, Data, Security (Victor - VETO), CISO, ISO Officer, Risk (Nadia - ESCALATION), FG-DPO (Aisha - INDEPENDENT), Privacy, Solution, Information, Network, Portfolio, Red Team (Raven - CHALLENGE), Erik (Manufacturing), Petra (R&D)

### Authority Types

- **VETO** — Security (Victor) can block
- **ESCALATION** — Risk (Nadia) can escalate
- **INDEPENDENT** — FG-DPO (Aisha) cannot be overruled
- **PATIENT SAFETY** — CMIO cannot be fast-tracked
- **CHALLENGE** — Red Team pre-mortem

### Hard Triage Floors

- `clinical-system` → mandatory CMIO, no fast-track
- `patient-data` → mandatory FG-DPO, DPIA required
- `decommission` → mandatory Process + Application review

## Project Structure

```
src/preflight/
├── api/              # FastAPI REST API (app.py)
├── archimate/        # ArchiMate XML parser
├── auth/             # AuthN (Entra ID), AuthZ (RBAC+ABAC), Audit (NEN 7513), Guardrails
├── citation/         # Citation processor (HYPERLINK/KEEP/REMOVE modes)
├── classify/         # Heuristic + LLM classification
├── cli/              # Click CLI (assess, full-assess, ingest, quick-scan)
├── db/               # SQLAlchemy models, session, DDL schema
├── embedding/        # Embedding router, contextual retrieval, pipeline
├── integrations/     # TOPdesk, LeanIX, Graph connectors
├── llm/              # LLM client (Ollama, NIM), router, parser
├── parsing/          # Document parsers (PDF, DOCX, MD, .archimate)
├── pipeline/          # Orchestrator, pipeline, quickscan
├── retrieval/         # pgvector store, enrichment, classify, reranker, retrieve
└── synthesis/         # Document generation (Jinja2 templates), diagrams
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PREFLIGHT_DATABASE_URL` | `~/.preflight/preflight.db` | SQLite (dev) or PostgreSQL+pgvector (prod) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `PREFLIGHT_LLM_MODEL` | `llama3.1:8b` | Default LLM model |

Copy `.env.example` to `.env` and fill in your values.

## Testing

```bash
python -m pytest src/tests/ -q           # Run all 287 tests
python -m pytest src/tests/test_smoke_e2e.py -v  # End-to-end smoke tests
python -m ruff check src/preflight/       # Lint
```

## Regulatory Context

Built for Dutch hospital environments, grounded in **ZiRA** (Ziekenhuis Referentie Architectuur):

- NEN 7510/7512/7513/7516/7517 (information security)
- AVG/GDPR (privacy)
- NIS2 (network & information security)
- MDR/IVDR (medical device regulation)
- AIVG 2022 (application integration)
- Wegiz (healthcare data exchange)
- EU AI Act (when applicable)

## License

Proprietary — internal use only.