# Preflight Pipeline Experiments

Autonomous experiment framework for tuning the Preflight ingestion + retrieval pipeline.
Adapted from karpathy/autoresearch patterns.

## Setup

To set up a new experiment run:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr12`). The branch `experiment/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b experiment/<tag>` from current master.
3. **Read the in-scope files**:
   - `experiment/program.md` — this file (agent instructions)
   - `experiment/config.py` — the file you modify (pipeline parameters)
   - `experiment/evaluate.py` — ground-truth QA evaluation (DO NOT MODIFY)
   - `experiment/runner.py` — fixed experiment harness (DO NOT MODIFY)
   - `experiment/qa_ground_truth.json` — QA pairs for evaluation (DO NOT MODIFY)
   - `src/preflight/embedding/chunking.py` — chunking implementation
   - `src/preflight/retrieval/store.py` — vector store implementation
   - `src/preflight/retrieval/retrieve.py` — per-persona RAG retrieval
   - `src/preflight/parsing/parsers.py` — PDF parsing
4. **Verify PDFs exist**: Check that the 6 PDFs are in the project root.
5. **Verify Ollama is running**: `ollama list` should show `nomic-embed-text` (or similar embedding model).
6. **Initialize results.tsv**: Create `experiment/results.tsv` with just the header row.
7. **Confirm and go**: Confirm setup looks good.

## What you CAN modify

- `experiment/config.json` — pipeline tuning parameters (the main "train.py")
- `src/preflight/embedding/chunking.py` — chunking strategies
- `src/preflight/parsing/parsers.py` — PDF parsing logic
- `src/preflight/retrieval/retrieve.py` — retrieval augmentation
- `src/preflight/retrieval/store.py` — vector store schema + queries
- `src/preflight/retrieval/index.py` — DocumentIndex protocol + filters

## What you CANNOT modify

- `experiment/runner.py` — fixed harness
- `experiment/evaluate.py` — ground-truth evaluation
- `experiment/qa_ground_truth.json` — QA pairs
- `experiment/program.md` — these instructions

## The metric

**Recall@5** is the primary metric (higher is better).
Tiebreakers: precision@5, then MRR.

These measure whether the pipeline retrieves the RIGHT source documents
when given domain-specific questions about NEN standards and architecture methodology.

## Config parameters

The `experiment/config.json` file controls:

### pdf (PDF parsing)
- `engine`: "pymupdf" | "marker" | "unstructured"
- `extract_tables`: bool — extract tables as Markdown
- `table_format`: "markdown" | "csv" | "html"
- `extract_images`: bool — render page images for vision model
- `image_vision_model`: "" | "qwen3:14b" — Ollama model for image descriptions
- `page_timeout_seconds`: int

### chunking
- `child_chunk_size`: int — child chunk size in tokens (retrieval unit)
- `child_overlap`: int — overlap between child chunks
- `parent_chunk_size`: int — parent section size (context expansion)
- `parent_overlap`: int
- `strategy`: "section_aware" | "semantic" | "recursive" | "hybrid"
- `preserve_tables`: bool — keep tables intact, don't split
- `table_row_per_chunk`: bool — one table row per chunk
- `regulatory_chunk_size`: int — specific for regulatory docs (NEN)
- `vendor_chunk_size`: int — specific for vendor docs
- `policy_chunk_size`: int — specific for policy/method docs (Novius)

### embedding
- `model`: "nomic-embed-text" | "mxbai-embed-large" | custom
- `dimensions`: int — 768 for nomic, 1024 for mxbai
- `batch_size`: int
- `router`: "ollama" | "voyage" | "bge"
- `content_type_routing`: bool — route different content types to different models

### retrieval
- `alpha`: float 0.0-1.0 — dense/keyword blend (0=keyword, 1=semantic)
- `top_k`: int — number of results to retrieve
- `reranker`: "identity" | "mxbai" | "hyde"
- `parent_expansion`: bool — expand child hits to parent context
- `parent_max_tokens`: int — max parent context to include
- `persona_augmentation`: bool — augment queries with persona domain keywords
- `hyde_enabled`: bool — use hypothetical document embeddings
- `min_score`: float — minimum similarity score threshold

### versioning
- `default_tag`: str — version tag for documents without explicit version
- `conflict_policy`: "newer_wins" | "both" | "warn" — how to handle version conflicts
- `warn_on_conflict`: bool
- `filter_by_version`: bool — only return results matching requested version
- `requested_version`: str — specific version to filter to

## Experiment areas

These are the high-impact areas to explore:

1. **Child chunk size vs recall**: Smaller chunks = more precise retrieval but less context. Try 256, 384, 512, 768, 1024.
2. **Parent expansion strategy**: Always expand? Only when table? Only on low scores?
3. **Alpha tuning**: NEN docs are keyword-heavy (control numbers like "08.01.03"). Try alpha 0.2, 0.5, 0.8.
4. **Table preservation**: Tables intact vs one-row-per-chunk vs no special handling.
5. **Section-aware chunking**: Split at `##` and `###` headers vs pure semantic splitting.
6. **Reranker impact**: No reranker vs MXBAI cross-encoder vs HyDE.
7. **Version filtering**: Filter by version vs return all and let LLM decide.
8. **Image/vision for diagrams**: Extract page images → qwen3:14b description vs skip images.

## The experiment loop

LOOP FOREVER:

1. Look at git state and current config
2. Modify `config.json` (and/or pipeline code) with an experimental idea
3. git commit
4. Run the experiment
5. Read results: `cat experiment/results.tsv | tail -5`
6. If recall@5 improved → keep the commit
7. If recall@5 equal or worse → git reset back to previous commit
8. Repeat

**Timeout**: Each experiment should take < 10 minutes. If longer, kill and treat as failure.

**NEVER STOP**: Do NOT pause to ask the human. The human might be asleep. You are autonomous.

## Simplicity criterion

All else being equal, simpler is better. A 0.01 recall improvement that adds 100 lines of complex code
is probably not worth it. A 0.01 recall improvement from DELETING code? Definitely keep.
Equal results with simpler code? Keep.