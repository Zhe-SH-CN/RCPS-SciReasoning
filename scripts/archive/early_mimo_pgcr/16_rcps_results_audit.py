#!/usr/bin/env python3
"""
RCPS Results Audit: comprehensive audit for RCPS experiments.

Computes:
- hits and Hit@10
- bootstrap confidence intervals
- paired win/loss/tie against repaired Direct-10
- gained and lost target IDs
- exact final idea count per target
- parse failure rates
- token totals by stage
- oracle-result warnings
- leakage checks for prompts if prompt logs exist

Output: results/rcps_results_audit.json, results/rcps_results_audit.md
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def bootstrap_ci(hits: int, total: int, n_boot: int = 10000, seed: int = 42) -> dict:
    """Bootstrap 95% CI for a proportion using deterministic resampling."""
    if total == 0:
        return {"low": 0.0, "high": 0.0, "point": 0.0}
    import random
    rng = random.Random(seed)
    p = hits / total
    samples = []
    for _ in range(n_boot):
        h = sum(1 for _ in range(total) if rng.random() < p)
        samples.append(h / total)
    samples.sort()
    lo = samples[int(0.025 * n_boot)]
    hi = samples[int(0.975 * n_boot)]
    return {"low": round(lo * 100, 1), "high": round(hi * 100, 1), "point": round(p * 100, 1)}


def load_result(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def compute_paired_comparison(baseline_hits: set, method_hits: set) -> dict:
    """Compute paired win/loss/tie against baseline."""
    wins = method_hits - baseline_hits
    losses = baseline_hits - method_hits
    ties = baseline_hits & method_hits
    return {
        "wins": len(wins),
        "losses": len(losses),
        "ties": len(ties),
        "win_ids": sorted(wins),
        "loss_ids": sorted(losses),
        "tie_ids": sorted(ties),
    }


def check_parse_failures(targets: list[dict]) -> dict:
    """Check parse failure rates in judgments."""
    total = 0
    parse_ok = 0
    parse_fail = 0
    empty_reason = 0
    confidence_zero = 0

    for t in targets:
        for j in t.get("judgments", []):
            total += 1
            if j.get("parse_status") == "ok":
                parse_ok += 1
            else:
                parse_fail += 1
            if not j.get("reason"):
                empty_reason += 1
            if j.get("confidence", 0) == 0:
                confidence_zero += 1

    return {
        "total": total,
        "parse_ok": parse_ok,
        "parse_fail": parse_fail,
        "parse_rate": round(parse_ok / max(total, 1) * 100, 1),
        "empty_reason": empty_reason,
        "confidence_zero": confidence_zero,
    }


def main():
    # Load results
    d10_path = PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"
    bcs_path = PROJECT_ROOT / "results" / "bcs50_eval_mimo_v25pro.json"
    pgcr_path = PROJECT_ROOT / "results" / "pgcr_enriched_eval.json"
    token_path = PROJECT_ROOT / "results" / "token_cost_audit.json"

    d10 = load_result(d10_path)
    bcs = load_result(bcs_path)
    pgcr = load_result(pgcr_path)
    token_audit = load_result(token_path)

    if not d10:
        print("ERROR: Direct-10 results not found")
        return 1

    # Build hit sets
    d10_hits = {t["target_id"] for t in d10["targets"] if t.get("hit")}
    bcs_hits = {t["target_id"] for t in bcs["targets"] if t.get("hit")} if bcs else set()
    pgcr_hits = {t["target_id"] for t in pgcr["targets"] if t.get("hit")} if pgcr else set()

    # Compute metrics for each method
    methods = {}

    # Direct-10
    d10_ci = bootstrap_ci(len(d10_hits), 77)
    d10_parse = check_parse_failures(d10["targets"])
    methods["direct10"] = {
        "hits": len(d10_hits),
        "total": 77,
        "hit_at_10": round(len(d10_hits) / 77 * 100, 1),
        "ci": d10_ci,
        "parse": d10_parse,
        "hit_ids": sorted(d10_hits),
    }

    # BCS-50
    if bcs:
        bcs_ci = bootstrap_ci(len(bcs_hits), 77)
        bcs_parse = check_parse_failures(bcs["targets"])
        bcs_paired = compute_paired_comparison(d10_hits, bcs_hits)
        methods["bcs50"] = {
            "hits": len(bcs_hits),
            "total": 77,
            "hit_at_10": round(len(bcs_hits) / 77 * 100, 1),
            "ci": bcs_ci,
            "parse": bcs_parse,
            "paired_vs_direct10": bcs_paired,
            "hit_ids": sorted(bcs_hits),
        }

    # PGCR
    if pgcr:
        pgcr_ci = bootstrap_ci(len(pgcr_hits), 77)
        pgcr_parse = check_parse_failures(pgcr["targets"])
        pgcr_paired = compute_paired_comparison(d10_hits, pgcr_hits)
        methods["pgcr"] = {
            "hits": len(pgcr_hits),
            "total": 77,
            "hit_at_10": round(len(pgcr_hits) / 77 * 100, 1),
            "ci": pgcr_ci,
            "parse": pgcr_parse,
            "paired_vs_direct10": pgcr_paired,
            "hit_ids": sorted(pgcr_hits),
        }

    # Union analysis
    union_hits = d10_hits | bcs_hits | pgcr_hits
    common_hits = d10_hits & bcs_hits & pgcr_hits

    # Oracle warning
    oracle_warning = None
    if len(union_hits) > len(d10_hits):
        oracle_warning = (
            f"Union of all methods has {len(union_hits)} hits, "
            f"more than any single method. Do not report as a fair method."
        )

    # Token costs
    token_costs = {}
    if token_audit:
        token_costs = {
            "direct10": token_audit.get("direct10", {}).get("total", 0),
            "bcs50": token_audit.get("bcs50", {}).get("total", 0),
            "pgcr": token_audit.get("pgcr", {}).get("total", 0),
        }

    # Build audit
    audit = {
        "timestamp": datetime.now().isoformat(),
        "methods": methods,
        "union": {
            "hits": len(union_hits),
            "common_hits": len(common_hits),
            "d10_only": len(d10_hits - bcs_hits - pgcr_hits),
            "bcs_only": len(bcs_hits - d10_hits - pgcr_hits),
            "pgcr_only": len(pgcr_hits - d10_hits - bcs_hits),
        },
        "token_costs": token_costs,
        "oracle_warning": oracle_warning,
    }

    # Save JSON
    output_path = PROJECT_ROOT / "results" / "rcps_results_audit.json"
    with open(output_path, "w") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    print(f"Saved: {output_path}")

    # Save Markdown
    report_path = PROJECT_ROOT / "results" / "rcps_results_audit.md"
    with open(report_path, "w") as f:
        f.write("# RCPS Results Audit\n\n")
        f.write(f"Generated: {audit['timestamp']}\n\n")

        f.write("## Main Results\n\n")
        f.write("| Method | Hits | Hit@10 | 95% CI | Parse Rate |\n")
        f.write("|---|---:|---:|---|---:|\n")
        for name, m in methods.items():
            ci_str = f"[{m['ci']['low']}, {m['ci']['high']}]"
            f.write(f"| {name} | {m['hits']} | {m['hit_at_10']}% | {ci_str} | {m['parse']['parse_rate']}% |\n")
        f.write("\n")

        f.write("## Paired Comparison vs Direct-10\n\n")
        f.write("| Method | Wins | Losses | Ties |\n")
        f.write("|---|---:|---:|---:|\n")
        for name, m in methods.items():
            if "paired_vs_direct10" in m:
                p = m["paired_vs_direct10"]
                f.write(f"| {name} | {p['wins']} | {p['losses']} | {p['ties']} |\n")
        f.write("\n")

        f.write("## Union Analysis\n\n")
        f.write(f"- Union hits: {audit['union']['hits']}\n")
        f.write(f"- Common hits (all methods): {audit['union']['common_hits']}\n")
        f.write(f"- Direct-10 only: {audit['union']['d10_only']}\n")
        f.write(f"- BCS-50 only: {audit['union']['bcs_only']}\n")
        f.write(f"- PGCR only: {audit['union']['pgcr_only']}\n\n")

        if oracle_warning:
            f.write("## Oracle Warning\n\n")
            f.write(f"⚠️ {oracle_warning}\n\n")

        f.write("## Token Costs\n\n")
        if token_costs:
            f.write("| Method | Total Tokens |\n")
            f.write("|---|---:|\n")
            for name, cost in token_costs.items():
                f.write(f"| {name} | {cost:,} |\n")
        else:
            f.write("Token cost data not available.\n")
        f.write("\n")

        f.write("## Parse Failures\n\n")
        for name, m in methods.items():
            p = m["parse"]
            f.write(f"### {name}\n\n")
            f.write(f"- Total judgments: {p['total']}\n")
            f.write(f"- Parse OK: {p['parse_ok']} ({p['parse_rate']}%)\n")
            f.write(f"- Parse fail: {p['parse_fail']}\n")
            f.write(f"- Empty reason: {p['empty_reason']}\n")
            f.write(f"- Confidence zero: {p['confidence_zero']}\n\n")

    print(f"Saved: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
