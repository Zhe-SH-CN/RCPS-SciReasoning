#!/usr/bin/env python3
"""ACML Results Audit: read JSON/JSONL result files and produce a structured audit.

Creates:
  - results/acml_results_audit.json
  - results/acml_results_audit.md

Computes:
  - hits / total / Hit@10 per method
  - overlaps between methods
  - full-set vs hard-case-only warnings
  - oracle-result warnings
  - token totals
  - candidate count distribution
  - judge confidence summary
  - missing metadata warnings
  - bootstrap 95% CI for Hit@10
"""

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
LOGS_DIR = PROJECT_ROOT / "logs"

# Result files to audit
RESULT_FILES = {
    "baseline": RESULTS_DIR / "baseline_mimo.json",
    "baseline_enriched": RESULTS_DIR / "acml_direct10_rejudge_mimo_v25pro.json",
    "bcs50": RESULTS_DIR / "bcs50_eval_mimo_v25pro.json",
    "pgcr": RESULTS_DIR / "pgcr_full.json",
    "pgcr_enriched": RESULTS_DIR / "pgcr_enriched_eval.json",
    "vanilla_expansion": RESULTS_DIR / "vanilla_expansion_eval.json",
}


def load_result(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


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


def candidate_count_distribution(targets: list[dict], method: str) -> dict:
    """Distribution of candidate counts per target."""
    counts = []
    for t in targets:
        if method == "baseline":
            counts.append(len(t.get("generated_ideas", [])))
        elif method == "pgcr":
            counts.append(t.get("num_candidates", len(t.get("selected_ideas", []))))
        elif method == "vanilla_expansion":
            counts.append(t.get("num_candidates", len(t.get("selected_ideas", []))))
    if not counts:
        return {}
    c = Counter(counts)
    return {
        "min": min(counts),
        "max": max(counts),
        "mean": round(sum(counts) / len(counts), 1),
        "distribution": dict(sorted(c.items())),
    }


def judge_confidence_summary(targets: list[dict]) -> dict:
    """Summary of judge confidence scores across all judgments."""
    confidences = []
    for t in targets:
        for j in t.get("judgments", []):
            c = j.get("confidence")
            if c is not None:
                confidences.append(float(c))
    if not confidences:
        return {}
    return {
        "count": len(confidences),
        "mean": round(sum(confidences) / len(confidences), 3),
        "min": round(min(confidences), 3),
        "max": round(max(confidences), 3),
        "hit_mean": round(
            sum(c for t in targets for j in t.get("judgments", []) if j.get("match") and (c := j.get("confidence")) is not None) /
            max(sum(1 for t in targets for j in t.get("judgments", []) if j.get("match")), 1), 3
        ),
        "miss_mean": round(
            sum(c for t in targets for j in t.get("judgments", []) if not j.get("match") and (c := j.get("confidence")) is not None) /
            max(sum(1 for t in targets for j in t.get("judgments", []) if not j.get("match")), 1), 3
        ),
    }


def check_metadata(result: dict, method: str) -> list[str]:
    """Check for missing or inconsistent metadata."""
    warnings = []
    top_keys = set(result.keys()) - {"targets"}
    expected = {"run_id", "model", "total_targets", "completed", "hits", "hit_at_10"}
    if method in ("pgcr", "vanilla_expansion"):
        expected.add("method")
        expected.add("judge_model")
    missing = expected - top_keys
    if missing:
        warnings.append(f"Missing top-level keys: {missing}")

    # Check method field consistency
    if method == "vanilla_expansion" and result.get("method") != "vanilla_expansion":
        warnings.append(f"Method field is '{result.get('method')}' instead of 'vanilla_expansion'")

    # Check for private paths in string values
    for k, v in result.items():
        if k == "targets":
            continue
        if isinstance(v, str) and ("/home/" in v or "/Users/" in v):
            warnings.append(f"Private path in {k}: {v[:80]}")

    return warnings


def compute_overlap(result_a: dict, result_b: dict) -> dict:
    """Compute hit-set overlap between two methods."""
    ids_a = {t["target_id"] for t in result_a["targets"] if t.get("hit")}
    ids_b = {t["target_id"] for t in result_b["targets"] if t.get("hit")}
    common = ids_a & ids_b
    only_a = ids_a - ids_b
    only_b = ids_b - ids_a
    return {
        "common_hits": len(common),
        "only_a": len(only_a),
        "only_b": len(only_b),
        "a_hits": len(ids_a),
        "b_hits": len(ids_b),
    }


def load_tokens_from_logs() -> dict:
    """Load token totals from experiment logs if available."""
    summary_path = LOGS_DIR / "experiment_summary.json"
    if not summary_path.exists():
        return {}
    with open(summary_path) as f:
        return json.load(f)


def main():
    audit = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "result_files": {},
        "methods": {},
        "overlaps": {},
        "oracle_warnings": [],
        "token_totals": {},
        "metadata_warnings": [],
        "enrichment_status": {},
    }

    # Load all results
    results = {}
    for name, path in RESULT_FILES.items():
        r = load_result(path)
        if r is None:
            audit["result_files"][name] = {"path": str(path), "status": "missing"}
            continue
        results[name] = r
        audit["result_files"][name] = {
            "path": str(path.name),
            "status": "found",
            "top_keys": [k for k in r if k != "targets"],
        }

    # Per-method analysis
    for name, r in results.items():
        targets = r.get("targets", [])
        total = r.get("total_targets", len(targets))
        completed = r.get("completed", len(targets))
        hits = r.get("hits", 0)
        hit_at_10 = r.get("hit_at_10", 0.0)

        # Recompute hits from targets for verification
        recomputed_hits = sum(1 for t in targets if t.get("hit"))

        method_info = {
            "total_targets": total,
            "completed": completed,
            "hits": hits,
            "hits_recomputed": recomputed_hits,
            "hit_at_10": hit_at_10,
            "hit_at_10_recomputed": round(recomputed_hits / max(completed, 1) * 100, 1),
            "is_full_set": completed == 77,
            "candidates": candidate_count_distribution(targets, name),
            "judge_confidence": judge_confidence_summary(targets),
            "metadata_warnings": check_metadata(r, name),
        }

        # Token info
        if "total_input_tokens" in r:
            method_info["total_input_tokens"] = r["total_input_tokens"]
        if "total_output_tokens" in r:
            method_info["total_output_tokens"] = r["total_output_tokens"]
        if "total_tokens" in r:
            method_info["total_tokens"] = r["total_tokens"]

        # Bootstrap CI
        ci = bootstrap_ci(recomputed_hits, completed)
        method_info["bootstrap_95ci"] = ci

        # Check recomputed vs reported
        if hits != recomputed_hits:
            method_info["warning"] = f"Reported hits ({hits}) != recomputed ({recomputed_hits})"

        audit["methods"][name] = method_info
        audit["metadata_warnings"].extend(
            f"[{name}] {w}" for w in method_info["metadata_warnings"]
        )

    # Oracle warning
    vanilla = results.get("vanilla_expansion")
    baseline = results.get("baseline")
    if vanilla and baseline:
        vanilla_targets = {t["target_id"] for t in vanilla["targets"]}
        baseline_targets = {t["target_id"] for t in baseline["targets"]}
        baseline_hits = {t["target_id"] for t in baseline["targets"] if t.get("hit")}
        baseline_misses = baseline_targets - baseline_hits

        if vanilla_targets == baseline_misses:
            audit["oracle_warnings"].append(
                "vanilla_expansion was evaluated ONLY on baseline misses (48 targets). "
                "Combined baseline+vanilla results are oracle-style and not a fair method."
            )
            # Compute oracle combined
            vanilla_hits = {t["target_id"] for t in vanilla["targets"] if t.get("hit")}
            oracle_hits = baseline_hits | vanilla_hits
            audit["oracle_warnings"].append(
                f"Oracle combined: {len(oracle_hits)}/77 = {round(len(oracle_hits)/77*100,1)}% — "
                "this must not be reported as the main method."
            )

    # Overlaps
    method_pairs = list(results.keys())
    for i, a in enumerate(method_pairs):
        for b in method_pairs[i+1:]:
            overlap = compute_overlap(results[a], results[b])
            audit["overlaps"][f"{a}_vs_{b}"] = overlap

    # Token totals from logs
    log_tokens = load_tokens_from_logs()
    if log_tokens:
        audit["token_totals"] = log_tokens

    # Enrichment status
    enriched_path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
    if enriched_path.exists():
        with open(enriched_path) as f:
            records = [json.loads(line) for line in f]
        non_empty = sum(1 for r in records if r.get("contribution"))
        audit["enrichment_status"] = {
            "path": str(enriched_path.name),
            "total": len(records),
            "non_empty_contributions": non_empty,
            "ready": non_empty == 77,
        }

    # Write JSON
    audit_path = RESULTS_DIR / "acml_results_audit.json"
    with open(audit_path, "w") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {audit_path}")

    # Write Markdown
    md_path = RESULTS_DIR / "acml_results_audit.md"
    with open(md_path, "w") as f:
        f.write("# ACML Results Audit\n\n")
        f.write(f"Generated: {audit['generated']}\n\n")

        # Methods table
        f.write("## Method Results\n\n")
        f.write("| Method | Targets | Completed | Hits | Hit@10 | 95% CI | Full-set |\n")
        f.write("|---|---:|---:|---:|---:|---|---|\n")
        for name, m in audit["methods"].items():
            ci = m.get("bootstrap_95ci", {})
            ci_str = f"[{ci.get('low', '?')}, {ci.get('high', '?')}]"
            full = "yes" if m["is_full_set"] else f"NO ({m['completed']}/77)"
            f.write(f"| {name} | {m['total_targets']} | {m['completed']} | {m['hits']} | {m['hit_at_10']}% | {ci_str} | {full} |\n")
        f.write("\n")

        # Overlaps
        f.write("## Hit-Set Overlaps\n\n")
        for pair, ov in audit["overlaps"].items():
            f.write(f"### {pair}\n\n")
            f.write(f"- Method A hits: {ov['a_hits']}\n")
            f.write(f"- Method B hits: {ov['b_hits']}\n")
            f.write(f"- Common hits: {ov['common_hits']}\n")
            f.write(f"- Only in A: {ov['only_a']}\n")
            f.write(f"- Only in B: {ov['only_b']}\n\n")

        # Oracle warnings
        if audit["oracle_warnings"]:
            f.write("## Oracle Warnings\n\n")
            for w in audit["oracle_warnings"]:
                f.write(f"⚠️ {w}\n\n")

        # Token totals
        f.write("## Token Usage\n\n")
        for name, m in audit["methods"].items():
            tokens = m.get("total_tokens") or (m.get("total_input_tokens", 0) + m.get("total_output_tokens", 0))
            f.write(f"- {name}: {tokens:,} tokens\n")
        f.write("\n")

        # Candidate counts
        f.write("## Candidate Counts\n\n")
        for name, m in audit["methods"].items():
            c = m.get("candidates", {})
            if c:
                f.write(f"- {name}: min={c.get('min')}, max={c.get('max')}, mean={c.get('mean')}\n")
        f.write("\n")

        # Judge confidence
        f.write("## Judge Confidence\n\n")
        for name, m in audit["methods"].items():
            jc = m.get("judge_confidence", {})
            if jc:
                f.write(f"- {name}: mean={jc.get('mean')}, hit_mean={jc.get('hit_mean')}, miss_mean={jc.get('miss_mean')}\n")
        f.write("\n")

        # Metadata warnings
        if audit["metadata_warnings"]:
            f.write("## Metadata Warnings\n\n")
            for w in audit["metadata_warnings"]:
                f.write(f"- {w}\n")
            f.write("\n")

        # Enrichment status
        es = audit.get("enrichment_status", {})
        if es:
            f.write("## Enrichment Status\n\n")
            f.write(f"- File: {es.get('path')}\n")
            f.write(f"- Total records: {es.get('total')}\n")
            f.write(f"- Non-empty contributions: {es.get('non_empty_contributions')}\n")
            f.write(f"- Ready for ACML judging: {es.get('ready')}\n\n")

        # Recomputation notes
        f.write("## Recomputation Notes\n\n")
        for name, m in audit["methods"].items():
            if m.get("warning"):
                f.write(f"- ⚠️ {name}: {m['warning']}\n")
            if m["hits"] == m["hits_recomputed"]:
                f.write(f"- ✅ {name}: reported hits match recomputed\n")
        f.write("\n")

    print(f"Wrote: {md_path}")
    print("\nAudit complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
