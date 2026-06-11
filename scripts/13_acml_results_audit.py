#!/usr/bin/env python3
"""
ACML Results Audit: Robust summarizer for experiment result files.

Reads JSON/JSONL result files directly and computes:
  - hits / total / Hit@10
  - overlaps between baseline, PGCR, and expansion
  - full-set vs hard-case-only warnings
  - oracle-result warnings
  - token totals from result files
  - candidate count distribution
  - judge confidence summary
  - missing metadata warnings
  - bootstrap confidence intervals

Outputs:
  - results/acml_results_audit.json
  - results/acml_results_audit.md

Does NOT rely on markdown summaries as ground truth.
"""

import json
import math
import os
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def bootstrap_ci(hits: int, total: int, n_boot: int = 10000, seed: int = 42) -> dict:
    """Bootstrap 95% CI for a proportion."""
    if total == 0:
        return {"low": 0.0, "high": 0.0, "mean": 0.0}
    rng = random.Random(seed)
    p_hat = hits / total
    samples = []
    for _ in range(n_boot):
        # Binomial bootstrap
        h = sum(1 for _ in range(total) if rng.random() < p_hat)
        samples.append(h / total)
    samples.sort()
    low = samples[int(0.025 * n_boot)]
    high = samples[int(0.975 * n_boot)]
    return {"low": round(low * 100, 1), "high": round(high * 100, 1), "mean": round(p_hat * 100, 1)}


def analyze_method(data: dict, method_name: str, is_hard_case_only: bool = False) -> dict:
    """Analyze a single result file."""
    targets = data.get("targets", [])
    total = len(targets)
    hits = sum(1 for t in targets if t.get("hit"))
    hit_at_10 = round(hits / max(total, 1) * 100, 1)
    ci = bootstrap_ci(hits, total)

    hit_ids = {t["target_id"] for t in targets if t.get("hit")}
    all_ids = {t["target_id"] for t in targets}

    # Token accounting
    total_input_tokens = data.get("total_input_tokens", 0)
    total_output_tokens = data.get("total_output_tokens", 0)
    total_tokens_field = data.get("total_tokens", 0)
    # Recount from targets if top-level is missing
    if not total_input_tokens and not total_tokens_field:
        for t in targets:
            gen = t.get("generation", {})
            total_input_tokens += gen.get("input_tokens", 0) or 0
            total_output_tokens += gen.get("output_tokens", 0) or 0
            for j in t.get("judgments", []):
                total_input_tokens += j.get("input_tokens", 0) or 0
                total_output_tokens += j.get("output_tokens", 0) or 0

    # Candidate count distribution
    candidate_counts = []
    for t in targets:
        nc = t.get("num_candidates")
        if nc is not None:
            candidate_counts.append(nc)
        elif "generated_ideas" in t:
            candidate_counts.append(len(t["generated_ideas"]))

    # Judge confidence for matched ideas
    match_confs = []
    all_confs = []
    for t in targets:
        for j in t.get("judgments", []):
            conf = j.get("confidence", 0)
            all_confs.append(conf)
            if j.get("match"):
                match_confs.append(conf)

    # Metadata checks
    warnings = []
    model = data.get("model") or data.get("judge_model", "")
    if not model:
        warnings.append("missing model field")
    if is_hard_case_only:
        warnings.append("evaluated on baseline-miss subset only (not full-set)")
    if "pgcr_full" in method_name.lower() and data.get("method") == "pgcr_full":
        pass  # expected
    elif data.get("method", "") != method_name and method_name != "baseline":
        warnings.append(f'method field says "{data.get("method")}" but analyzed as "{method_name}"')

    result = {
        "method": method_name,
        "model": model,
        "total_targets": data.get("total_targets", total),
        "completed": total,
        "hits": hits,
        "hit_at_10": hit_at_10,
        "ci_95": ci,
        "hit_ids": sorted(hit_ids),
        "all_ids": sorted(all_ids),
        "is_hard_case_only": is_hard_case_only,
        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
            "from_field": total_tokens_field,
        },
        "warnings": warnings,
    }

    if candidate_counts:
        result["candidate_counts"] = {
            "n": len(candidate_counts),
            "min": min(candidate_counts),
            "max": max(candidate_counts),
            "mean": round(sum(candidate_counts) / len(candidate_counts), 1),
        }

    if all_confs:
        result["confidence"] = {
            "all_ideas": {
                "n": len(all_confs),
                "mean": round(sum(all_confs) / len(all_confs), 2),
            },
        }
    if match_confs:
        result["confidence"]["matched_ideas"] = {
            "n": len(match_confs),
            "min": round(min(match_confs), 2),
            "max": round(max(match_confs), 2),
            "mean": round(sum(match_confs) / len(match_confs), 2),
        }

    return result


def compute_overlaps(analyses: dict[str, dict]) -> dict:
    """Compute hit overlaps between methods."""
    baseline = analyses.get("baseline", {})
    pgcr = analyses.get("pgcr", {})
    vanilla = analyses.get("vanilla_expansion", {})

    b_hits = set(baseline.get("hit_ids", []))
    p_hits = set(pgcr.get("hit_ids", []))
    v_hits = set(vanilla.get("hit_ids", []))
    b_all = set(baseline.get("all_ids", []))

    overlaps = {}

    if b_hits and p_hits:
        overlaps["pgcr_vs_baseline"] = {
            "pgcr_hits_also_in_baseline": sorted(p_hits & b_hits),
            "pgcr_hits_not_in_baseline": sorted(p_hits - b_hits),
            "baseline_hits_lost_by_pgcr": sorted(b_hits - p_hits),
            "count_pgcr_overlaps_baseline": len(p_hits & b_hits),
            "count_pgcr_new_hits": len(p_hits - b_hits),
            "count_baseline_lost": len(b_hits - p_hits),
        }

    if b_hits and v_hits:
        # Vanilla was run on baseline misses only
        vanilla_targets = set(vanilla.get("all_ids", []))
        expected_hard = b_all - b_hits
        oracle_hits = b_hits | v_hits

        overlaps["vanilla_expansion"] = {
            "vanilla_target_count": len(vanilla_targets),
            "expected_hard_case_count": len(expected_hard),
            "is_hard_case_only": vanilla_targets == expected_hard,
            "vanilla_new_hits": sorted(v_hits),
            "oracle_combined_hits": sorted(oracle_hits),
            "oracle_combined_count": len(oracle_hits),
        }

    return overlaps


def check_eval_data(eval_path: Path) -> dict:
    """Check enriched eval data quality."""
    if not eval_path.exists():
        return {"exists": False, "warnings": ["enriched eval file not found"]}

    records = []
    with open(eval_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    empty_contrib = sum(1 for r in records if not r.get("contribution", "").strip())
    has_source = sum(1 for r in records if r.get("contribution_source", "") not in ("", "missing"))
    path_leaks = sum(1 for r in records if "/home/" in r.get("contribution", "") or "/Users/" in r.get("contribution", ""))
    pred_counts = [len(r.get("predecessors", [])) for r in records]

    return {
        "exists": True,
        "total_records": len(records),
        "non_empty_contributions": len(records) - empty_contrib,
        "empty_contributions": empty_contrib,
        "with_contribution_source": has_source,
        "path_leaks": path_leaks,
        "avg_predecessors": round(sum(pred_counts) / max(len(pred_counts), 1), 1),
        "warnings": [] if empty_contrib == 0 else [f"{empty_contrib} records have empty contributions"],
    }


def generate_markdown(analyses: dict, overlaps: dict, eval_check: dict) -> str:
    """Generate the markdown audit report."""
    lines = [
        "# ACML Results Audit",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "**This report is computed from JSON result files, not from markdown summaries.**",
        "",
        "## Method Comparison",
        "",
        "| Method | Targets | Hits | Hit@10 | 95% CI | Full-set? |",
        "|--------|--------:|-----:|-------:|--------|-----------|",
    ]

    for name in ["baseline", "pgcr", "vanilla_expansion"]:
        a = analyses.get(name, {})
        if not a:
            continue
        full = "Yes" if not a.get("is_hard_case_only") else "No (hard-case only)"
        ci = a.get("ci_95", {})
        ci_str = f"[{ci.get('low', '?')}%, {ci.get('high', '?')}%]"
        label = name.replace("_", " ").title()
        lines.append(f"| {label} | {a.get('completed', '?')} | {a.get('hits', '?')} | {a.get('hit_at_10', '?')}% | {ci_str} | {full} |")

    # Oracle combined
    oracle = overlaps.get("vanilla_expansion", {})
    if oracle.get("oracle_combined_count"):
        lines.append(f"| Oracle Combined | 77 | {oracle['oracle_combined_count']} | {round(oracle['oracle_combined_count']/77*100, 1)}% | — | **NOT FAIR** |")

    lines.append("")

    # Overlap analysis
    if "pgcr_vs_baseline" in overlaps:
        o = overlaps["pgcr_vs_baseline"]
        lines.extend([
            "## PGCR vs Baseline Overlap",
            "",
            f"- PGCR hits also in baseline: {o['count_pgcr_overlaps_baseline']}",
            f"- PGCR new hits (baseline misses): {o['count_pgcr_new_hits']}",
            f"- Baseline hits lost by PGCR: {o['count_baseline_lost']}",
            "",
        ])

    if "vanilla_expansion" in overlaps:
        o = overlaps["vanilla_expansion"]
        lines.extend([
            "## Vanilla Expansion Analysis",
            "",
            f"- Evaluated on {o['vanilla_target_count']} targets (baseline misses)",
            f"- Hard-case-only: {o['is_hard_case_only']}",
            f"- New hits: {o['oracle_combined_count'] - len(analyses.get('baseline', {}).get('hit_ids', []))}",
            f"- Oracle combined hits: {o['oracle_combined_count']} / 77 = {round(o['oracle_combined_count']/77*100, 1)}%",
            "",
            "**WARNING: Oracle combined uses knowledge of baseline failures. Not a fair standalone method.**",
            "",
        ])

    # Per-method details
    for name in ["baseline", "pgcr", "vanilla_expansion"]:
        a = analyses.get(name, {})
        if not a:
            continue
        label = name.replace("_", " ").title()
        lines.extend([
            f"## {label} Details",
            "",
            f"- Model: {a.get('model', 'unknown')}",
            f"- Completed: {a.get('completed', '?')} / {a.get('total_targets', '?')}",
        ])

        if a.get("candidate_counts"):
            cc = a["candidate_counts"]
            lines.append(f"- Candidates: min={cc['min']}, max={cc['max']}, mean={cc['mean']}")

        tok = a.get("tokens", {})
        if tok.get("input") or tok.get("output"):
            lines.append(f"- Tokens: input={tok.get('input', 0):,}, output={tok.get('output', 0):,}")
        elif tok.get("from_field"):
            lines.append(f"- Tokens (from file): {tok['from_field']:,}")

        if a.get("confidence"):
            c = a["confidence"]
            if "matched_ideas" in c:
                m = c["matched_ideas"]
                lines.append(f"- Match confidence: mean={m['mean']}, min={m['min']}, max={m['max']} (n={m['n']})")

        if a.get("warnings"):
            lines.append("")
            for w in a["warnings"]:
                lines.append(f"  ⚠ {w}")

        lines.append("")

    # Eval data check
    lines.extend([
        "## Eval Data Quality",
        "",
        f"- Enriched file exists: {eval_check.get('exists', False)}",
    ])
    if eval_check.get("exists"):
        lines.extend([
            f"- Total records: {eval_check.get('total_records', 0)}",
            f"- Non-empty contributions: {eval_check.get('non_empty_contributions', 0)}",
            f"- Empty contributions: {eval_check.get('empty_contributions', 0)}",
            f"- Avg predecessors: {eval_check.get('avg_predecessors', 0)}",
            f"- Path leaks: {eval_check.get('path_leaks', 0)}",
        ])
    if eval_check.get("warnings"):
        for w in eval_check["warnings"]:
            lines.append(f"  ⚠ {w}")
    lines.append("")

    # Global warnings
    all_warnings = []
    for name, a in analyses.items():
        for w in a.get("warnings", []):
            all_warnings.append(f"[{name}] {w}")
    for w in eval_check.get("warnings", []):
        all_warnings.append(f"[eval_data] {w}")

    if all_warnings:
        lines.extend([
            "## All Warnings",
            "",
        ])
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def main():
    results_dir = PROJECT_ROOT / "results"
    eval_path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
    output_json = results_dir / "acml_results_audit.json"
    output_md = results_dir / "acml_results_audit.md"

    # Load and analyze each method
    analyses = {}

    baseline_path = results_dir / "baseline_mimo.json"
    if baseline_path.exists():
        data = load_json(baseline_path)
        analyses["baseline"] = analyze_method(data, "baseline")

    pgcr_path = results_dir / "pgcr_full.json"
    if pgcr_path.exists():
        data = load_json(pgcr_path)
        analyses["pgcr"] = analyze_method(data, "pgcr_full")

    vanilla_path = results_dir / "vanilla_expansion_eval.json"
    if vanilla_path.exists():
        data = load_json(vanilla_path)
        # Check if it was run on hard-case only
        baseline_ids = set(analyses.get("baseline", {}).get("all_ids", []))
        baseline_hits = set(analyses.get("baseline", {}).get("hit_ids", []))
        hard_case_ids = baseline_ids - baseline_hits
        vanilla_ids = {t["target_id"] for t in data.get("targets", [])}
        is_hard = vanilla_ids == hard_case_ids
        analyses["vanilla_expansion"] = analyze_method(data, "vanilla_expansion", is_hard_case_only=is_hard)

    # Compute overlaps
    overlaps = compute_overlaps(analyses)

    # Check eval data
    eval_check = check_eval_data(eval_path)

    # Build output
    audit = {
        "generated": datetime.now().isoformat(),
        "methods": analyses,
        "overlaps": overlaps,
        "eval_data": eval_check,
    }

    # Write JSON
    with open(output_json, "w") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    # Write markdown
    md = generate_markdown(analyses, overlaps, eval_check)
    with open(output_md, "w") as f:
        f.write(md)

    print(f"Audit complete:")
    print(f"  JSON: {output_json}")
    print(f"  Markdown: {output_md}")
    print()
    for name, a in analyses.items():
        ci = a.get("ci_95", {})
        print(f"  {name}: {a['hits']}/{a['completed']} = {a['hit_at_10']}% CI[{ci.get('low')}%, {ci.get('high')}%]")


if __name__ == "__main__":
    main()
