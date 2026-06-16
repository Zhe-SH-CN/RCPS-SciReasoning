#!/usr/bin/env python3
"""
Audit Sci-Reasoning reset outputs from scripts 33/34.

Local-only; makes no API calls. It recomputes key metrics, checks exact target
title/contribution leakage in generated/final ideas, and scans for obvious
secret or local-path material.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_DATA = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
FAITH_SCRIPT = PROJECT_ROOT / "scripts" / "33_scireasoning_faithful_reproduction.py"

SECRET_PATTERNS = [
    re.compile(r"\b(?:XIAOMI_MIMO_API_KEY|SJTU_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY)\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|authorization|bearer)\b\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,}"),
]
LOCAL_PATH_RE = re.compile(r"(/home/[^\s\"']+|/Users/[^\s\"']+|[A-Za-z]:\\Users\\[^\s\"']+)")


def load_eval(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    with path.open() as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                rows[rec["target_id"]] = rec
    return rows


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def idea_blob(ideas: list[dict[str, Any]]) -> str:
    return json.dumps(ideas, ensure_ascii=False).lower()


def scan_file_text(path: Path) -> list[str]:
    text = path.read_text(errors="replace")
    issues = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append("secret_like_pattern")
            break
    if LOCAL_PATH_RE.search(text):
        issues.append("local_absolute_path")
    return issues


def load_faith_module() -> Any:
    spec = importlib.util.spec_from_file_location("faith", FAITH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {FAITH_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def audit_rejudge_or_direct(obj: dict[str, Any], eval_data: dict[str, dict[str, Any]], faith: Any) -> dict[str, Any]:
    issues = []
    targets = obj.get("targets", [])
    judgments = 0
    judge_status = Counter()
    generation_status = Counter()
    hits = 0
    exact_leakage = []
    idea_count_bad = []
    judgment_count_bad = []
    excluded_target_title = 0
    excluded_target_contribution = 0
    recovered_parse = 0

    for record in targets:
        target_id = record.get("target_id")
        eval_rec = eval_data.get(target_id, {})
        title = (eval_rec.get("title") or record.get("paper_title") or "").lower()
        contribution = (eval_rec.get("contribution") or record.get("contribution") or "").lower()
        ideas = record.get("generated_ideas") or record.get("final_ideas") or []
        if len(ideas) != obj.get("k", 10):
            idea_count_bad.append(f"{target_id}:{len(ideas)}")
        text = idea_blob(ideas)
        if title and title in text:
            exact_leakage.append(f"{target_id}:target_title")
        if contribution and len(contribution) > 30 and contribution in text:
            exact_leakage.append(f"{target_id}:contribution")
        if record.get("generation"):
            generation_status[record["generation"].get("parse_status", "missing")] += 1
        if len(record.get("judgments", [])) != obj.get("k", 10):
            judgment_count_bad.append(f"{target_id}:{len(record.get('judgments', []))}")
        excluded_target_title += record.get("context_metadata", {}).get("excluded_target_title_contexts", 0)
        excluded_target_contribution += record.get("context_metadata", {}).get("excluded_target_contribution_contexts", 0)
        hit = False
        for judgment in record.get("judgments", []):
            judgments += 1
            parse_status = judgment.get("parse_status", "missing")
            recovered = None
            if parse_status != "ok" and obj.get("protocol") == "paper_json":
                recovered = faith.parse_json_response(judgment.get("raw_response", ""))
                if isinstance(recovered, dict) and isinstance(recovered.get("is_match"), bool):
                    parse_status = "ok"
                    recovered_parse += 1
            judge_status[parse_status] += 1
            if judgment.get("is_match") is True or (isinstance(recovered, dict) and recovered.get("is_match") is True):
                hit = True
        if hit:
            hits += 1

    if idea_count_bad:
        issues.append(f"idea_count_bad:{','.join(idea_count_bad[:10])}")
    if judgment_count_bad:
        issues.append(f"judgment_count_bad:{','.join(judgment_count_bad[:10])}")
    if exact_leakage:
        issues.append(f"exact_leakage:{','.join(exact_leakage[:10])}")

    judge_ok = judge_status.get("ok", 0)
    judge_fail = judgments - judge_ok
    return {
        "kind": obj.get("kind"),
        "protocol": obj.get("protocol"),
        "targets": len(targets),
        "completed": obj.get("completed", len(targets)),
        "hits": hits,
        "hit_at_10": round(hits / max(len(targets), 1) * 100, 2),
        "total_judgments": judgments,
        "judge_parse_ok": judge_ok,
        "judge_parse_fail": judge_fail,
        "judge_parse_rate": round(judge_ok / max(judgments, 1) * 100, 2),
        "judge_status": dict(judge_status),
        "generation_status": dict(generation_status),
        "excluded_target_title_contexts": excluded_target_title,
        "excluded_target_contribution_contexts": excluded_target_contribution,
        "judge_parse_recovered_by_audit": recovered_parse,
        "issues": issues,
    }


def audit_method(obj: dict[str, Any], eval_data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    issues = []
    targets = obj.get("targets", [])
    exact_leakage = []
    selected_bad = []
    parse_counts = Counter()
    candidates = 0
    selected = 0
    excluded_target_title = 0
    excluded_target_contribution = 0
    for record in targets:
        target_id = record.get("target_id")
        eval_rec = eval_data.get(target_id, {})
        title = (eval_rec.get("title") or record.get("paper_title") or "").lower()
        contribution = (eval_rec.get("contribution") or "").lower()
        final_ideas = record.get("generated_ideas", [])
        if len(final_ideas) != obj.get("k", 10):
            selected_bad.append(f"{target_id}:{len(final_ideas)}")
        text = idea_blob(final_ideas + record.get("candidate_pool", []))
        if title and title in text:
            exact_leakage.append(f"{target_id}:target_title")
        if contribution and len(contribution) > 30 and contribution in text:
            exact_leakage.append(f"{target_id}:contribution")
        candidates += len(record.get("candidate_pool", []))
        selected += len(final_ideas)
        excluded_target_title += record.get("context_metadata", {}).get("excluded_target_title_contexts", 0)
        excluded_target_contribution += record.get("context_metadata", {}).get("excluded_target_contribution_contexts", 0)
        for call in record.get("generation_calls", []):
            parse_counts[call.get("parse_status", "missing")] += 1
    if selected_bad:
        issues.append(f"selected_count_bad:{','.join(selected_bad[:10])}")
    if exact_leakage:
        issues.append(f"exact_leakage:{','.join(exact_leakage[:10])}")
    return {
        "kind": obj.get("kind"),
        "method": obj.get("method"),
        "targets": len(targets),
        "completed": obj.get("completed", len(targets)),
        "total_candidates": candidates,
        "total_selected": selected,
        "generation_status": dict(parse_counts),
        "excluded_target_title_contexts": excluded_target_title,
        "excluded_target_contribution_contexts": excluded_target_contribution,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Sci-Reasoning reset output")
    parser.add_argument("input")
    parser.add_argument("--eval-data", default=str(DEFAULT_EVAL_DATA))
    parser.add_argument("--report")
    parser.add_argument("--min-judge-parse-rate", type=float, default=95.0)
    parser.add_argument("--require-context-source", choices=["cache"])
    args = parser.parse_args()

    input_path = Path(args.input)
    obj = json.loads(input_path.read_text())
    eval_data = load_eval(Path(args.eval_data))
    faith = load_faith_module()
    if obj.get("kind") == "scireasoning_method_candidates":
        summary = audit_method(obj, eval_data)
    else:
        summary = audit_rejudge_or_direct(obj, eval_data, faith)
    file_issues = scan_file_text(input_path)
    summary["file"] = display_path(input_path)
    summary["file_issues"] = file_issues
    summary["generated"] = datetime.now().isoformat()

    verdict = "PASS"
    reasons = []
    if summary.get("issues"):
        verdict = "FAIL"
        reasons.extend(summary["issues"])
    if file_issues:
        verdict = "FAIL"
        reasons.extend(file_issues)
    if summary.get("total_judgments") and summary.get("judge_parse_rate", 0) < args.min_judge_parse_rate:
        verdict = "FAIL"
        reasons.append(f"judge_parse_rate_below_{args.min_judge_parse_rate}")
    if args.require_context_source and obj.get("context_source") != args.require_context_source:
        verdict = "FAIL"
        reasons.append(f"context_source_not_{args.require_context_source}:{obj.get('context_source')}")
    summary["verdict"] = verdict
    summary["reasons"] = reasons

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
