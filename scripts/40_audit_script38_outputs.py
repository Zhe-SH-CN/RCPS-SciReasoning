#!/usr/bin/env python3
"""
Audit Script38 direct/method JSON outputs without changing scores.

Checks are intentionally mechanical:
- recompute Hit@10 from per-target hit_at_k;
- verify judgment counts match parsed/selected generated ideas;
- verify method outputs use the official-v4 binary judge protocol marker;
- scan generated ideas for exact target title/contribution;
- report cached-context exact target-text caveats separately;
- scan output/log files for current local secret values without printing them.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)


def load_env_secrets(path: Path):
    secrets = []
    if not path.exists():
        return secrets
    for line in path.read_text(errors="ignore").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if len(value) >= 8 and any(token in key for token in ["KEY", "TOKEN", "SECRET"]):
            secrets.append((key, value))
    return secrets


def scan_secrets(paths: list[Path], secrets: list[tuple[str, str]]):
    hits = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        for key, value in secrets:
            if value in text:
                hits.append({"secret_name": key, "path": str(path)})
    return hits


def joined_generated(record):
    parts = [str(record.get("generated_ideas_raw", ""))]
    parts.extend(str(item) for item in record.get("generated_ideas", []))
    for candidate in record.get("candidate_pool", []):
        if isinstance(candidate, dict):
            parts.append(str(candidate.get("idea_text", "")))
        else:
            parts.append(str(candidate))
    for call in record.get("generation_calls", []):
        if isinstance(call, dict):
            parts.append(str(call.get("raw_response", "")))
    return "\n".join(parts)


def joined_context(record):
    parts = []
    for pred in record.get("predecessor_details", []):
        parts.append(str(pred.get("title", "")))
        parts.append(str(pred.get("original_query", "")))
        parts.append(str(pred.get("content", "")))
    return "\n".join(parts)


def audit_output(
    path: Path,
    log_paths: list[Path],
    require_method_protocol: bool,
    expect_total: int | None,
    expect_model: str | None,
    expect_method: str | None,
):
    data = load_json(path)
    summary = data.get("summary", {})
    results = data.get("results", [])
    issues = []
    caveats = []

    total = len(results)
    computed_hits = sum(1 for row in results if row.get("hit_at_k"))
    summary_total = summary.get("total_papers")
    summary_hits = summary.get("hits")
    summary_rate = summary.get("hit_rate_percent")
    computed_rate = round(computed_hits / total * 100, 2) if total else 0.0

    if summary_total != total:
        issues.append(f"summary_total_mismatch:{summary_total}!={total}")
    if expect_total is not None and total != expect_total:
        issues.append(f"expected_total_mismatch:{total}!={expect_total}")
    if expect_model is not None and summary.get("model") != expect_model:
        issues.append(f"expected_model_mismatch:{summary.get('model')}!={expect_model}")
    actual_method = summary.get("method", "direct")
    if expect_method is not None and actual_method != expect_method:
        issues.append(f"expected_method_mismatch:{actual_method}!={expect_method}")
    if summary_hits != computed_hits:
        issues.append(f"summary_hits_mismatch:{summary_hits}!={computed_hits}")
    if summary_rate is not None and not math.isclose(float(summary_rate), computed_rate, abs_tol=0.01):
        issues.append(f"summary_rate_mismatch:{summary_rate}!={computed_rate}")

    if require_method_protocol and summary.get("evaluation_protocol") != "official_v4_binary_judge_hit_at_k":
        issues.append("missing_official_v4_binary_judge_protocol_marker")
    if require_method_protocol:
        if not str(summary.get("official_runner", "")).endswith("scripts/38_scireasoning_official_cache_exa.py"):
            issues.append("missing_script38_official_runner_provenance")
        if summary.get("official_judge_function") != "judge_similarity":
            issues.append("missing_official_judge_function_provenance")
        if summary.get("official_parser_function") != "parse_ideas_from_response":
            issues.append("missing_official_parser_function_provenance")
        if summary.get("method_scope") != "candidate_generation_and_target_hidden_selection_only":
            issues.append("missing_method_scope_provenance")

    generated_exact = []
    context_exact = []
    judgment_mismatch = []
    over_k = []
    zero_ideas = []
    idea_counts = []
    judgment_counts = []
    for idx, row in enumerate(results):
        title = (row.get("paper_title") or "").strip()
        contribution = (row.get("contribution") or "").strip()
        ideas = row.get("generated_ideas", [])
        judgments = row.get("judgments", [])
        idea_counts.append(len(ideas))
        judgment_counts.append(len(judgments))
        if len(ideas) != len(judgments):
            judgment_mismatch.append(idx)
        if len(ideas) > int(summary.get("k", 10)):
            over_k.append(idx)
        if len(ideas) == 0:
            zero_ideas.append(idx)
        generated_text = joined_generated(row)
        context_text = joined_context(row)
        if title and title in generated_text:
            generated_exact.append({"idx": idx, "type": "title", "hit": bool(row.get("hit_at_k"))})
        if contribution and contribution in generated_text:
            generated_exact.append({"idx": idx, "type": "contribution", "hit": bool(row.get("hit_at_k"))})
        if title and title in context_text:
            context_exact.append({"idx": idx, "type": "title", "hit": bool(row.get("hit_at_k"))})
        if contribution and contribution in context_text:
            context_exact.append({"idx": idx, "type": "contribution", "hit": bool(row.get("hit_at_k"))})

    if judgment_mismatch:
        issues.append(f"judgment_count_mismatch:{len(judgment_mismatch)}")
    if over_k:
        issues.append(f"more_than_k_generated_ideas:{len(over_k)}")
    if zero_ideas:
        issues.append(f"zero_generated_ideas:{len(zero_ideas)}")
    if generated_exact:
        issues.append(f"generated_exact_target_text:{len(generated_exact)}")
    if context_exact:
        caveats.append(f"context_exact_target_text:{len(context_exact)}")

    log_errors = []
    for log_path in log_paths:
        if not log_path.exists():
            continue
        text = log_path.read_text(errors="ignore")
        for pattern in ["Traceback", "API error", "Read timed out", "ReadTimeout", " 429 ", " 401 ", " 403 "]:
            if pattern in text:
                log_errors.append({"path": str(log_path), "pattern": pattern})
    if log_errors:
        issues.append(f"log_error_patterns:{len(log_errors)}")

    secret_hits = scan_secrets([path, *log_paths], load_env_secrets(PROJECT_ROOT / ".env"))
    if secret_hits:
        issues.append(f"secret_hits:{len(secret_hits)}")

    verdict = "PASS" if not issues else "FAIL"
    report = {
        "verdict": verdict,
        "path": str(path),
        "model": summary.get("model"),
        "method": summary.get("method", "direct"),
        "total_papers": total,
        "hits": computed_hits,
        "hit_rate_percent": computed_rate,
        "idea_count_min": min(idea_counts) if idea_counts else 0,
        "idea_count_max": max(idea_counts) if idea_counts else 0,
        "judgment_count_min": min(judgment_counts) if judgment_counts else 0,
        "judgment_count_max": max(judgment_counts) if judgment_counts else 0,
        "issues": issues,
        "caveats": caveats,
        "generated_exact_target_text": generated_exact[:20],
        "context_exact_target_text": context_exact[:20],
        "secret_hit_count": len(secret_hits),
    }
    print(json.dumps(report, indent=2))
    return 0 if verdict == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Script38 direct/method JSON outputs")
    parser.add_argument("json_path")
    parser.add_argument("--log", action="append", default=[])
    parser.add_argument("--require-method-protocol", action="store_true")
    parser.add_argument("--expect-total", type=int)
    parser.add_argument("--expect-model")
    parser.add_argument("--expect-method")
    args = parser.parse_args()
    return audit_output(
        Path(args.json_path),
        [Path(item) for item in args.log],
        args.require_method_protocol,
        args.expect_total,
        args.expect_model,
        args.expect_method,
    )


if __name__ == "__main__":
    raise SystemExit(main())
