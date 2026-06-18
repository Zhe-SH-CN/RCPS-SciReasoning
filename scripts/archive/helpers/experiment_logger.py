#!/usr/bin/env python3
"""
Persistent experiment logger for tracking token usage, timing, and progress.

Writes to logs/experiment_log.jsonl - appends after every target.
Also maintains a running summary in logs/experiment_summary.json.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

_log_lock = Lock()


def _ensure_log_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_target_completion(
    run_name: str,
    target_id: str,
    stage: str,  # "generation", "scoring", "selection", "evaluation"
    num_api_calls: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    elapsed_seconds: float = 0,
    num_candidates: int = 0,
    hit: bool = False,
    extra: dict = None,
):
    """Log one target's completion. Thread-safe append."""
    _ensure_log_dir()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "run_name": run_name,
        "target_id": target_id,
        "stage": stage,
        "num_api_calls": num_api_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "elapsed_seconds": round(elapsed_seconds, 1),
        "num_candidates": num_candidates,
        "hit": hit,
    }
    if extra:
        entry.update(extra)

    with _log_lock:
        with open(LOG_DIR / "experiment_log.jsonl", "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Update summary
    _update_summary(run_name, stage, input_tokens, output_tokens, num_api_calls, hit)


def _update_summary(run_name, stage, input_tokens, output_tokens, num_api_calls, hit):
    """Update running summary file."""
    summary_path = LOG_DIR / "experiment_summary.json"

    with _log_lock:
        summary = {}
        if summary_path.exists():
            try:
                with open(summary_path) as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                summary = {}

        if run_name not in summary:
            summary[run_name] = {
                "stage": stage,
                "started": datetime.now().isoformat(),
                "targets_completed": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_api_calls": 0,
                "hits": 0,
            }

        run = summary[run_name]
        run["targets_completed"] += 1
        run["total_input_tokens"] += input_tokens
        run["total_output_tokens"] += output_tokens
        run["total_api_calls"] += num_api_calls
        run["hits"] += 1 if hit else 0
        run["hit_at_10"] = round(run["hits"] / max(run["targets_completed"], 1) * 100, 1)
        run["last_updated"] = datetime.now().isoformat()

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)


def get_summary(run_name: str = None) -> dict:
    """Get current experiment summary."""
    summary_path = LOG_DIR / "experiment_summary.json"
    if not summary_path.exists():
        return {}
    with open(summary_path) as f:
        summary = json.load(f)
    if run_name:
        return summary.get(run_name, {})
    return summary
