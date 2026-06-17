#!/usr/bin/env python3
"""Build no-API analysis tables for the Script38/39 RCPS study."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "results" / "analysis" / "20260617_rcps_no_api"

ROWS = {
    "gemini-3.1-pro-low": {
        "slug": "gemini_low",
        "direct": ROOT / "results/experiments/20260616_script38_mimo_gemini_full77/gemini_cache_exa_77t.json",
        "bcs": ROOT / "results/experiments/20260616_script38_methods_full77/bcs_gemini_low_77t.json",
        "rcps": ROOT / "results/experiments/20260616_script38_methods_full77/rcps_gemini_low_77t.json",
    },
    "gemini-pro-agent": {
        "slug": "gemini_pro_agent",
        "direct": ROOT / "results/experiments/20260616_script38_mimo_gemini_full77/gemini_pro_agent_cache_exa_77t.json",
        "bcs": ROOT / "results/experiments/20260616_script38_methods_full77/bcs_gemini_pro_agent_77t.json",
        "rcps": ROOT / "results/experiments/20260616_script38_methods_full77/rcps_gemini_pro_agent_77t.json",
    },
    "gemini-3-flash-agent": {
        "slug": "gemini_3_flash_agent",
        "direct": ROOT / "results/experiments/20260616_script38_gemini_baselines/gemini_3_flash_agent_cache_exa_77t.json",
        "bcs": ROOT / "results/experiments/20260616_script38_methods_full77/bcs_gemini_3_flash_agent_77t.json",
        "rcps": ROOT / "results/experiments/20260616_script38_methods_full77/rcps_gemini_3_flash_agent_77t.json",
    },
}


def load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def hit_map(data: dict) -> dict[int, bool]:
    return {int(r["paper_idx"]): bool(r.get("hit_at_k")) for r in data["results"]}


def by_idx(data: dict) -> dict[int, dict]:
    return {int(r["paper_idx"]): r for r in data["results"]}


def idea_counts(data: dict) -> list[int]:
    return [int(r.get("ideas_generated", len(r.get("generated_ideas", [])))) for r in data["results"]]


def median(xs: list[int]) -> float:
    ys = sorted(xs)
    n = len(ys)
    if n == 0:
        return 0.0
    return float(ys[n // 2]) if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def exact_p(new: int, lost: int) -> float:
    n = new + lost
    if n == 0:
        return 1.0
    x = min(new, lost)
    tail = sum(math.comb(n, i) for i in range(x + 1)) / (2**n)
    return min(1.0, 2 * tail)


def selected_source(record: dict, selected_idx: int) -> str:
    direct_count = sum(1 for c in record.get("candidate_pool", []) if c.get("source") == "direct_anchor")
    anchor_count = min(6, direct_count)
    return "anchor" if selected_idx < anchor_count else "fill"


def rcps_source_summary(data: dict) -> dict:
    anchor_targets = 0
    fill_targets = 0
    both_targets = 0
    no_hit_targets = 0
    selected_ideas = 0
    selected_anchor_ideas = 0
    selected_fill_ideas = 0
    matching_anchor_ideas = 0
    matching_fill_ideas = 0
    for r in data["results"]:
        judgments = r.get("judgments", [])
        selected_ideas += len(judgments)
        sources = []
        for j in judgments:
            idx = int(j.get("idea_idx", 0))
            src = selected_source(r, idx)
            if src == "anchor":
                selected_anchor_ideas += 1
            else:
                selected_fill_ideas += 1
            if j.get("is_match"):
                sources.append(src)
                if src == "anchor":
                    matching_anchor_ideas += 1
                else:
                    matching_fill_ideas += 1
        if "anchor" in sources and "fill" in sources:
            both_targets += 1
        elif "anchor" in sources:
            anchor_targets += 1
        elif "fill" in sources:
            fill_targets += 1
        else:
            no_hit_targets += 1
    return {
        "target_hits_anchor_only": anchor_targets,
        "target_hits_fill_only": fill_targets,
        "target_hits_both": both_targets,
        "target_no_hit": no_hit_targets,
        "selected_ideas": selected_ideas,
        "selected_anchor_ideas": selected_anchor_ideas,
        "selected_fill_ideas": selected_fill_ideas,
        "matching_anchor_ideas": matching_anchor_ideas,
        "matching_fill_ideas": matching_fill_ideas,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    main_rows = []
    paired_rows = []
    source_rows = []
    target_rows = []
    cost_rows = []

    combined_new = 0
    combined_lost = 0
    combined_direct_hits = 0
    combined_rcps_hits = 0
    combined_total = 0

    loaded = {}
    for model, paths in ROWS.items():
        loaded[model] = {m: load(p) for m, p in paths.items() if m != "slug"}
        for method, data in loaded[model].items():
            summary = data["summary"]
            counts = idea_counts(data)
            main_rows.append({
                "model": model,
                "method": method,
                "targets": summary["total_papers"],
                "hits": summary["hits"],
                "hit_at_10_percent": f'{summary["hit_rate_percent"]:.2f}',
                "idea_count_min": min(counts),
                "idea_count_median": f"{median(counts):.1f}",
                "idea_count_max": max(counts),
            })
            cost = summary.get("cost", {})
            cost_rows.append({
                "model": model,
                "method": method,
                "input_tokens": cost.get("input_tokens", ""),
                "output_tokens": cost.get("output_tokens", ""),
                "total_tokens": (
                    int(cost.get("input_tokens", 0) or 0) + int(cost.get("output_tokens", 0) or 0)
                ),
                "runtime_minutes": summary.get("runtime_minutes", ""),
                "parse_status_counts": json.dumps(summary.get("generation_parse_status_counts", {}), sort_keys=True),
            })

        direct = hit_map(loaded[model]["direct"])
        direct_by_idx = by_idx(loaded[model]["direct"])
        for method in ("bcs", "rcps"):
            method_hits = hit_map(loaded[model][method])
            ids = sorted(set(direct) & set(method_hits))
            new = sum((not direct[i]) and method_hits[i] for i in ids)
            lost = sum(direct[i] and (not method_hits[i]) for i in ids)
            both = sum(direct[i] and method_hits[i] for i in ids)
            neither = sum((not direct[i]) and (not method_hits[i]) for i in ids)
            net = new - lost
            paired_rows.append({
                "model": model,
                "comparison": f"{method}_vs_direct",
                "both_hit": both,
                "neither_hit": neither,
                "new_hits": new,
                "lost_direct_hits": lost,
                "net_hits": net,
                "exact_p": f"{exact_p(new, lost):.4f}",
            })
            if method == "rcps":
                combined_new += new
                combined_lost += lost
                combined_direct_hits += sum(direct[i] for i in ids)
                combined_rcps_hits += sum(method_hits[i] for i in ids)
                combined_total += len(ids)

        source = rcps_source_summary(loaded[model]["rcps"])
        source_rows.append({"model": model, **source})

        rcps_by_idx = by_idx(loaded[model]["rcps"])
        for idx, direct_hit in direct.items():
            rcps_hit = bool(rcps_by_idx[idx].get("hit_at_k"))
            if (not direct_hit) and rcps_hit:
                transition = "new_hit"
            elif direct_hit and (not rcps_hit):
                transition = "lost_direct_hit"
            elif direct_hit and rcps_hit:
                transition = "preserved_hit"
            else:
                transition = "neither_hit"
            match_sources = [
                selected_source(rcps_by_idx[idx], int(j.get("idea_idx", 0)))
                for j in rcps_by_idx[idx].get("judgments", [])
                if j.get("is_match")
            ]
            target_rows.append({
                "model": model,
                "paper_idx": idx,
                "paper_title": direct_by_idx[idx].get("paper_title", ""),
                "direct_hit": int(direct_hit),
                "rcps_hit": int(rcps_hit),
                "transition": transition,
                "rcps_match_sources": "+".join(sorted(set(match_sources))) if match_sources else "",
            })

    paired_rows.append({
        "model": "combined_model_target_rows",
        "comparison": "rcps_vs_direct",
        "both_hit": "",
        "neither_hit": "",
        "new_hits": combined_new,
        "lost_direct_hits": combined_lost,
        "net_hits": combined_new - combined_lost,
        "exact_p": f"{exact_p(combined_new, combined_lost):.4f}",
    })

    write_csv(OUT_DIR / "main_results.csv", main_rows)
    write_csv(OUT_DIR / "paired_new_lost.csv", paired_rows)
    write_csv(OUT_DIR / "rcps_source_analysis.csv", source_rows)
    write_csv(OUT_DIR / "target_transitions.csv", target_rows)
    write_csv(OUT_DIR / "cost_parse.csv", cost_rows)

    report = f"""# RCPS No-API Analysis Tables

Generated by `scripts/43_build_rcps_no_api_analysis.py`.

No model or Exa API calls were made. All tables are derived from existing JSON files under `results/experiments/`.

## Main Result

| Model | Direct | BCS | RCPS | RCPS - Direct |
|---|---:|---:|---:|---:|
"""
    for model in ROWS:
        vals = {r["method"]: r for r in main_rows if r["model"] == model}
        d = vals["direct"]
        r = vals["rcps"]
        diff = int(r["hits"]) - int(d["hits"])
        report += (
            f"| `{model}` | {d['hits']}/77 = {d['hit_at_10_percent']}% | "
            f"{vals['bcs']['hits']}/77 = {vals['bcs']['hit_at_10_percent']}% | "
            f"{r['hits']}/77 = {r['hit_at_10_percent']}% | {diff:+d} hits |\n"
        )
    report += f"""
Mean over model-target rows: Direct {combined_direct_hits}/{combined_total} = {combined_direct_hits/combined_total*100:.2f}%, RCPS {combined_rcps_hits}/{combined_total} = {combined_rcps_hits/combined_total*100:.2f}%.

Combined paired RCPS vs Direct: new hits {combined_new}, lost Direct hits {combined_lost}, net {combined_new-combined_lost}, exact paired p={exact_p(combined_new, combined_lost):.4f}.

## Output Files

- `main_results.csv`
- `paired_new_lost.csv`
- `rcps_source_analysis.csv`
- `target_transitions.csv`
- `cost_parse.csv`

## Claim Boundary

The result supports a protocol-scoped claim of consistent modest improvement across three Gemini-family model rows. It does not support a statistical-significance claim or exact Sci-Reasoning reproduction claim.
"""
    (OUT_DIR / "report.md").write_text(report)
    print(f"Wrote no-API analysis to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
