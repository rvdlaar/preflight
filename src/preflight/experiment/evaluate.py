"""
Preflight QA evaluation — ground-truth retrieval quality measurement.

This is our "val_bpb". We measure:
- recall@k: fraction of relevant sources found in top-k results
- precision@k: fraction of top-k results that are relevant
- MRR: mean reciprocal rank of first relevant result

The agent NEVER modifies this file. It is the ground truth.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


@dataclass
class QAPair:
    question: str
    relevant_source_ids: list[str]
    relevant_sections: list[str] = field(default_factory=list)
    persona_id: str = ""
    language: str = "nl"
    difficulty: str = "medium"

    @staticmethod
    def from_dict(d: dict) -> QAPair:
        return QAPair(
            question=d["question"],
            relevant_source_ids=d.get("relevant_source_ids", []),
            relevant_sections=d.get("relevant_sections", []),
            persona_id=d.get("persona_id", ""),
            language=d.get("language", "nl"),
            difficulty=d.get("difficulty", "medium"),
        )


@dataclass
class EvalMetrics:
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    precision_at_10: float
    mrr: float
    per_question: list[dict] = field(default_factory=list)


def _recall(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)


def _precision(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / k


def _reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    for i, item in enumerate(retrieved, 1):
        if item in relevant:
            return 1.0 / i
    return 0.0


async def evaluate_qa(
    qa_path: str,
    config=None,
) -> EvalMetrics:
    """Evaluate retrieval quality against ground-truth QA pairs.

    For each question:
    1. Run retrieval with the question
    2. Compare retrieved source_ids against relevant_source_ids
    3. Compute recall@5, recall@10, precision@5, precision@10, MRR
    """
    qa_file = Path(qa_path)
    if not qa_file.exists():
        raise FileNotFoundError(f"QA ground truth not found: {qa_path}")

    with open(qa_file) as f:
        qa_data = json.load(f)

    pairs = [QAPair.from_dict(d) for d in qa_data.get("questions", [])]

    if not pairs:
        return EvalMetrics(
            recall_at_5=0.0,
            recall_at_10=0.0,
            precision_at_5=0.0,
            precision_at_10=0.0,
            mrr=0.0,
        )

    from preflight.experiment.config import load_config

    cfg = config or load_config()

    from preflight.embedding.client import EmbeddingRouter
    from preflight.retrieval.store import get_global_store

    store = get_global_store()
    if cfg.embedding.router == "local":
        embedding_router = EmbeddingRouter.from_local(
            model=cfg.embedding.model,
            dimensions=cfg.embedding.dimensions,
        )
    else:
        embedding_router = EmbeddingRouter.from_ollama(model=cfg.embedding.model)

    per_question: list[dict] = []
    recalls_5: list[float] = []
    recalls_10: list[float] = []
    precisions_5: list[float] = []
    precisions_10: list[float] = []
    rrs: list[float] = []

    for pair in pairs:
        try:
            query_vector = await embedding_router.embed_query(pair.question, "regulatory")
        except Exception as e:
            logger.warning(
                "Embedding failed for question %d (%s): %s — scoring 0.0",
                len(per_question) + 1,
                pair.question[:50],
                e,
            )
            query_vector = None

        if query_vector is None:
            per_question.append(
                {
                    "question": pair.question,
                    "retrieved": [],
                    "recall@5": 0.0,
                    "recall@10": 0.0,
                    "precision@5": 0.0,
                    "precision@10": 0.0,
                    "mrr": 0.0,
                }
            )
            recalls_5.append(0.0)
            recalls_10.append(0.0)
            precisions_5.append(0.0)
            precisions_10.append(0.0)
            rrs.append(0.0)
            continue

        try:
            results = await store.search(
                query_vector=query_vector,
                query_text=pair.question,
                top_k=10,
                min_score=0.001,
            )
            retrieved_ids = [r.source_id for r in results]
        except Exception as e:
            logger.warning(
                "Search failed for question %d (%s): %s — returning empty results",
                len(per_question) + 1,
                pair.question[:50],
                e,
            )
            retrieved_ids = []

        relevant = set(pair.relevant_source_ids)
        r5 = _recall(retrieved_ids, relevant, 5)
        r10 = _recall(retrieved_ids, relevant, 10)
        p5 = _precision(retrieved_ids, relevant, 5)
        p10 = _precision(retrieved_ids, relevant, 10)
        rr = _reciprocal_rank(retrieved_ids, relevant)

        per_question.append(
            {
                "question": pair.question,
                "retrieved": retrieved_ids[:10],
                "relevant": list(relevant),
                "recall@5": r5,
                "recall@10": r10,
                "precision@5": p5,
                "precision@10": p10,
                "mrr": rr,
            }
        )

        recalls_5.append(r5)
        recalls_10.append(r10)
        precisions_5.append(p5)
        precisions_10.append(p10)
        rrs.append(rr)

    n = len(pairs)
    return EvalMetrics(
        recall_at_5=sum(recalls_5) / n,
        recall_at_10=sum(recalls_10) / n,
        precision_at_5=sum(precisions_5) / n,
        precision_at_10=sum(precisions_10) / n,
        mrr=sum(rrs) / n,
        per_question=per_question,
    )
