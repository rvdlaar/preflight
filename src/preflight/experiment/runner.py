"""
Preflight experiment runner — fixed harness for autonomous pipeline experiments.

This is the "prepare.py" of our autoresearch setup. It:
1. Ingests configured documents through the pipeline
2. Runs a ground-truth QA evaluation
3. Logs results to experiments.tsv
4. Returns pass/fail for the agent loop

The agent NEVER modifies this file. It only modifies pipeline config via
experiment/config.py (the "train.py" equivalent).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_FILE = PROJECT_ROOT / "experiment" / "results.tsv"
QA_GROUND_TRUTH = PROJECT_ROOT / "experiment" / "qa_ground_truth.json"


@dataclass
class ExperimentResult:
    commit: str
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    precision_at_10: float
    mrr: float
    total_chunks: int
    ingestion_seconds: float
    eval_seconds: float
    peak_memory_mb: float
    status: str
    description: str

    @property
    def primary_metric(self) -> float:
        return self.recall_at_5

    def to_tsv_row(self) -> str:
        return (
            f"{self.commit}\t{self.recall_at_5:.4f}\t{self.recall_at_10:.4f}\t"
            f"{self.precision_at_5:.4f}\t{self.precision_at_10:.4f}\t"
            f"{self.mrr:.4f}\t{self.total_chunks}\t"
            f"{self.ingestion_seconds:.1f}\t{self.eval_seconds:.1f}\t"
            f"{self.peak_memory_mb:.1f}\t{self.status}\t{self.description}"
        )


def _get_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _get_peak_memory_mb() -> float:
    try:
        import os as _os
        import resource

        page_size = _os.getpagesize()
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * page_size / (1024 * 1024)
    except Exception:
        return 0.0


def init_results_file():
    if not RESULTS_FILE.exists():
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "commit\trecall@5\trecall@10\tprecision@5\tprecision@10\t"
            "mrr\tchunks\tingest_s\teval_s\tmemory_mb\tstatus\tdescription"
        )
        RESULTS_FILE.write_text(header + "\n")


def log_result(result: ExperimentResult):
    init_results_file()
    with open(RESULTS_FILE, "a") as f:
        f.write(result.to_tsv_row() + "\n")


async def run_experiment(
    description: str = "baseline",
    config_path: str | None = None,
    qa_path: str | None = None,
    timeout_seconds: int = 600,
) -> ExperimentResult:
    """Run a full experiment: ingest → evaluate → log.

    This is the fixed harness. The agent changes config, we run, we measure.
    """
    from preflight.experiment.evaluate import evaluate_qa
    from preflight.experiment.config import load_config, apply_config

    commit = _get_commit()
    config = load_config(config_path)
    apply_config(config)

    qa_file = qa_path or str(QA_GROUND_TRUTH)
    if not Path(qa_file).exists():
        return ExperimentResult(
            commit=commit,
            recall_at_5=0.0,
            recall_at_10=0.0,
            precision_at_5=0.0,
            precision_at_10=0.0,
            mrr=0.0,
            total_chunks=0,
            ingestion_seconds=0.0,
            eval_seconds=0.0,
            peak_memory_mb=0.0,
            status="crash",
            description=f"No QA ground truth at {qa_file}",
        )

    t0 = time.monotonic()
    try:
        from preflight.experiment.ingest import ingest_all_pdfs

        total_chunks = await ingest_all_pdfs(config)
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        return ExperimentResult(
            commit=commit,
            recall_at_5=0.0,
            recall_at_10=0.0,
            precision_at_5=0.0,
            precision_at_10=0.0,
            mrr=0.0,
            total_chunks=0,
            ingestion_seconds=time.monotonic() - t0,
            eval_seconds=0.0,
            peak_memory_mb=_get_peak_memory_mb(),
            status="crash",
            description=f"Ingestion error: {e}",
        )
    ingest_seconds = time.monotonic() - t0

    t1 = time.monotonic()
    try:
        metrics = await evaluate_qa(qa_file, config)
    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        return ExperimentResult(
            commit=commit,
            recall_at_5=0.0,
            recall_at_10=0.0,
            precision_at_5=0.0,
            precision_at_10=0.0,
            mrr=0.0,
            total_chunks=total_chunks,
            ingestion_seconds=ingest_seconds,
            eval_seconds=time.monotonic() - t1,
            peak_memory_mb=_get_peak_memory_mb(),
            status="crash",
            description=f"Evaluation error: {e}",
        )
    eval_seconds = time.monotonic() - t1

    result = ExperimentResult(
        commit=commit,
        recall_at_5=metrics.recall_at_5,
        recall_at_10=metrics.recall_at_10,
        precision_at_5=metrics.precision_at_5,
        precision_at_10=metrics.precision_at_10,
        mrr=metrics.mrr,
        total_chunks=total_chunks,
        ingestion_seconds=ingest_seconds,
        eval_seconds=eval_seconds,
        peak_memory_mb=_get_peak_memory_mb(),
        status="keep",
        description=description,
    )

    log_result(result)
    return result


def check_improvement(prev: ExperimentResult, curr: ExperimentResult) -> bool:
    """Return True if curr is an improvement over prev.

    Primary metric: recall@5 (higher is better).
    Tiebreaker: precision@5, then MRR.
    """
    if curr.recall_at_5 > prev.recall_at_5:
        return True
    if curr.recall_at_5 == prev.recall_at_5:
        if curr.precision_at_5 > prev.precision_at_5:
            return True
        if curr.precision_at_5 == prev.precision_at_5 and curr.mrr > prev.mrr:
            return True
    return False


def read_last_result() -> ExperimentResult | None:
    if not RESULTS_FILE.exists():
        return None
    lines = RESULTS_FILE.read_text().strip().split("\n")
    if len(lines) < 2:
        return None
    last = lines[-1].split("\t")
    if len(last) < 12:
        return None
    return ExperimentResult(
        commit=last[0],
        recall_at_5=float(last[1]),
        recall_at_10=float(last[2]),
        precision_at_5=float(last[3]),
        precision_at_10=float(last[4]),
        mrr=float(last[5]),
        total_chunks=int(last[6]),
        ingestion_seconds=float(last[7]),
        eval_seconds=float(last[8]),
        peak_memory_mb=float(last[9]),
        status=last[10],
        description=last[11],
    )
