"""
Preflight experiment framework — AutoResearch patterns for pipeline tuning.

Adapted from karpathy/autoresearch for our ingestion + retrieval pipeline.
The agent modifies pipeline config (chunking, embedding, retrieval parameters),
runs experiments against a ground-truth QA set, and keeps improvements.

Architecture mirrors autoresearch:
  program.md  — agent instructions (what to experiment on)
  runner.py   — fixed harness: run pipeline, evaluate, log results (prepare.py)
  evaluate.py — ground-truth QA evaluation (the "val_bpb")
  pipeline.py — configurable pipeline params (the "train.py" the agent edits)

The metric is **recall@k + precision@k** on domain-specific QA pairs.
Lower is NOT better here — higher recall and precision = better pipeline.
"""

from __future__ import annotations
