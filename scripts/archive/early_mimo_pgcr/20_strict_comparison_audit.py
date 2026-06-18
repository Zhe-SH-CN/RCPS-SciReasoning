#!/usr/bin/env python3
"""
Audit strict same-judge Direct-10 vs RCPS results.

This script is intentionally post-hoc analysis only: it reads completed strict
evaluation JSON files and writes traceable JSON/Markdown summaries. It does not
call MiMo.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def result_by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["target_id"]: t for t in result.get("targets", [])}


def parse_summary(result: dict[str, Any]) -> dict[str, Any]:
    judgments = [j for t in result.get("targets", []) for j in t.get("judgments", [])]
    total = len(judgments)
    ok = sum(1 for j in judgments if j.get("parse_status") == "ok")
    fail_status = Counter(j.get("parse_status", "missing") for j in judgments if j.get("parse_status") != "ok")
    return {
        "total_judgments": total,
        "parse_ok": ok,
        "parse_fail": total - ok,
        "parse_rate": round(ok / max(total, 1) * 100, 1),
        "parse_fail_status": dict(sorted(fail_status.items())),
    }


def target_hit(target: dict[str, Any]) -> bool:
    return any(j.get("parse_status") == "ok" and j.get("match") is True for j in target.get("judgments", []))


def matching_judgments(target: dict[str, Any]) -> list[dict[str, Any]]:
    return [j for j in target.get("judgments", []) if j.get("parse_status") == "ok" and j.get("match") is True]


def first_direct_rank(target: dict[str, Any]) -> int | None:
    ranks = []
    for j in matching_judgments(target):
        if j.get("slot_source", "direct") == "direct":
            idx = j.get("idea_index")
            if isinstance(idx, int):
                ranks.append(idx + 1)
    return min(ranks) if ranks else None


def slot_hit_flags(target: dict[str, Any]) -> dict[str, bool]:
    direct = False
    expansion = False
    for j in matching_judgments(target):
        slot = str(j.get("slot_source", "direct"))
        if slot == "direct":
            direct = True
        if slot.startswith("expansion"):
            expansion = True
    return {"direct": direct, "expansion": expansion}


def method_summary(result: dict[str, Any]) -> dict[str, Any]:
    targets = result.get("targets", [])
    hits = sum(1 for t in targets if target_hit(t))
    judgments = [j for t in targets for j in t.get("judgments", [])]
    return {
        "method": result.get("method"),
        "prompt_version": result.get("prompt_version"),
        "criterion": result.get("criterion"),
        "completed": len(targets),
        "hits": hits,
        "hit_at_10": round(hits / max(len(targets), 1) * 100, 1),
        "parse": parse_summary(result),
        "total_input_tokens": sum(j.get("input_tokens") or 0 for j in judgments),
        "total_output_tokens": sum(j.get("output_tokens") or 0 for j in judgments),
        "total_tokens": sum(j.get("total_tokens") or 0 for j in judgments),
        "hit_ids": sorted(t["target_id"] for t in targets if target_hit(t)),
    }


def compare(direct: dict[str, Any], rcps: dict[str, Any], k_direct: int) -> dict[str, Any]:
    direct_by_id = result_by_id(direct)
    rcps_by_id = result_by_id(rcps)
    common_ids = sorted(set(direct_by_id) & set(rcps_by_id))
    direct_only_ids = sorted(set(direct_by_id) - set(rcps_by_id))
    rcps_only_ids = sorted(set(rcps_by_id) - set(direct_by_id))

    direct_hits = {tid for tid in common_ids if target_hit(direct_by_id[tid])}
    rcps_hits = {tid for tid in common_ids if target_hit(rcps_by_id[tid])}
    wins = sorted(rcps_hits - direct_hits)
    losses = sorted(direct_hits - rcps_hits)
    ties_hit = sorted(direct_hits & rcps_hits)
    ties_miss = sorted(set(common_ids) - direct_hits - rcps_hits)

    direct_tail_hits = []
    direct_tail_rank_by_id = {}
    for tid in direct_hits:
        rank = first_direct_rank(direct_by_id[tid])
        if rank is not None and rank > k_direct:
            direct_tail_hits.append(tid)
            direct_tail_rank_by_id[tid] = rank

    bound_violations = []
    for tid in losses:
        rank = first_direct_rank(direct_by_id[tid])
        if rank is not None and rank <= k_direct:
            bound_violations.append({"target_id": tid, "first_direct_rank": rank})

    slot_sources = {}
    expansion_only_gain_ids = []
    rcps_direct_hit_ids = []
    rcps_expansion_hit_ids = []
    rcps_both_slot_hit_ids = []

    for tid in common_ids:
        flags = slot_hit_flags(rcps_by_id[tid])
        slot_sources[tid] = flags
        if flags["direct"]:
            rcps_direct_hit_ids.append(tid)
        if flags["expansion"]:
            rcps_expansion_hit_ids.append(tid)
        if flags["direct"] and flags["expansion"]:
            rcps_both_slot_hit_ids.append(tid)
        if tid in wins and flags["expansion"] and not flags["direct"]:
            expansion_only_gain_ids.append(tid)

    target_rows = []
    for tid in common_ids:
        direct_hit = tid in direct_hits
        rcps_hit = tid in rcps_hits
        flags = slot_sources[tid]
        target_rows.append(
            {
                "target_id": tid,
                "target_title": direct_by_id[tid].get("target_title", rcps_by_id[tid].get("target_title", "")),
                "direct_hit": direct_hit,
                "rcps_hit": rcps_hit,
                "paired_outcome": "win" if rcps_hit and not direct_hit else "loss" if direct_hit and not rcps_hit else "tie",
                "direct_first_rank": first_direct_rank(direct_by_id[tid]),
                "rcps_direct_slot_hit": flags["direct"],
                "rcps_expansion_slot_hit": flags["expansion"],
                "direct_matches": [
                    {
                        "idea_index": j.get("idea_index"),
                        "idea_title": j.get("idea_title"),
                        "confidence": j.get("confidence"),
                        "reason": j.get("reason"),
                    }
                    for j in matching_judgments(direct_by_id[tid])
                ],
                "rcps_matches": [
                    {
                        "idea_index": j.get("idea_index"),
                        "slot_source": j.get("slot_source"),
                        "idea_title": j.get("idea_title"),
                        "confidence": j.get("confidence"),
                        "reason": j.get("reason"),
                    }
                    for j in matching_judgments(rcps_by_id[tid])
                ],
            }
        )

    audit = {
        "timestamp": datetime.now().isoformat(),
        "k_direct": k_direct,
        "direct": method_summary(direct),
        "rcps": method_summary(rcps),
        "common_targets": len(common_ids),
        "direct_only_targets": direct_only_ids,
        "rcps_only_targets": rcps_only_ids,
        "paired": {
            "wins": len(wins),
            "losses": len(losses),
            "ties_hit": len(ties_hit),
            "ties_miss": len(ties_miss),
            "win_ids": wins,
            "loss_ids": losses,
            "tie_hit_ids": ties_hit,
            "tie_miss_ids": ties_miss,
        },
        "direct_hit_loss_bound": {
            "bound_name": f"DirectTail(k={k_direct})",
            "direct_tail_hits": len(direct_tail_hits),
            "direct_tail_hit_ids": sorted(direct_tail_hits),
            "direct_tail_rank_by_id": direct_tail_rank_by_id,
            "observed_direct_hit_losses": len(losses),
            "bound_satisfied": len(bound_violations) == 0 and len(losses) <= len(direct_tail_hits),
            "bound_violations": bound_violations,
        },
        "slot_source_analysis": {
            "rcps_hits_explained_by_direct_slots": len([tid for tid in rcps_hits if slot_sources[tid]["direct"]]),
            "rcps_hits_with_expansion_slot_match": len([tid for tid in rcps_hits if slot_sources[tid]["expansion"]]),
            "rcps_hits_with_both_direct_and_expansion_matches": len([tid for tid in rcps_hits if slot_sources[tid]["direct"] and slot_sources[tid]["expansion"]]),
            "expansion_only_target_gains": len(expansion_only_gain_ids),
            "expansion_only_gain_ids": sorted(expansion_only_gain_ids),
            "rcps_direct_hit_ids": sorted(rcps_direct_hit_ids),
            "rcps_expansion_hit_ids": sorted(rcps_expansion_hit_ids),
            "rcps_both_slot_hit_ids": sorted(rcps_both_slot_hit_ids),
        },
        "claim_gate": {
            "improvement_hits": len(rcps_hits) - len(direct_hits),
            "passes_min_plus_2_hits": len(rcps_hits) - len(direct_hits) >= 2,
            "has_expansion_only_gains": len(expansion_only_gain_ids) > 0,
            "parse_failures_below_2_percent": (
                parse_summary(direct)["parse_fail"] + parse_summary(rcps)["parse_fail"]
            )
            / max(parse_summary(direct)["total_judgments"] + parse_summary(rcps)["total_judgments"], 1)
            < 0.02,
        },
        "targets": target_rows,
    }
    audit["claim_gate"]["rcps_improvement_paper_allowed"] = (
        audit["claim_gate"]["passes_min_plus_2_hits"]
        and audit["claim_gate"]["has_expansion_only_gains"]
        and audit["claim_gate"]["parse_failures_below_2_percent"]
        and audit["direct_hit_loss_bound"]["bound_satisfied"]
    )
    return audit


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Strict RCPS Comparison Audit\n\n")
        f.write(f"Generated: {audit['timestamp']}\n\n")
        f.write(f"- Direct method: `{audit['direct']['method']}`\n")
        f.write(f"- RCPS method: `{audit['rcps']['method']}`\n")
        f.write(f"- Prompt version: `{audit['direct']['prompt_version']}` / `{audit['rcps']['prompt_version']}`\n")
        f.write(f"- k direct slots for bound: {audit['k_direct']}\n\n")

        f.write("## Main Results\n\n")
        f.write("| Method | Completed | Hits | Hit@10 | Parse OK | Parse Fail | Tokens |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for name in ["direct", "rcps"]:
            m = audit[name]
            f.write(
                f"| {name} | {m['completed']} | {m['hits']} | {m['hit_at_10']}% | "
                f"{m['parse']['parse_ok']} | {m['parse']['parse_fail']} | {m['total_tokens']:,} |\n"
            )
        f.write("\n")

        p = audit["paired"]
        f.write("## Paired Comparison\n\n")
        f.write("| Wins | Losses | Tie Hits | Tie Misses |\n")
        f.write("|---:|---:|---:|---:|\n")
        f.write(f"| {p['wins']} | {p['losses']} | {p['ties_hit']} | {p['ties_miss']} |\n\n")

        s = audit["slot_source_analysis"]
        f.write("## Slot Source Analysis\n\n")
        f.write(f"- RCPS hits explained by direct slots: {s['rcps_hits_explained_by_direct_slots']}\n")
        f.write(f"- RCPS hits with expansion slot match: {s['rcps_hits_with_expansion_slot_match']}\n")
        f.write(f"- RCPS hits with both direct and expansion matches: {s['rcps_hits_with_both_direct_and_expansion_matches']}\n")
        f.write(f"- Expansion-only target gains: {s['expansion_only_target_gains']}\n")
        if s["expansion_only_gain_ids"]:
            f.write(f"- Expansion-only gain IDs: {', '.join(s['expansion_only_gain_ids'])}\n")
        f.write("\n")

        b = audit["direct_hit_loss_bound"]
        f.write("## Direct-Hit Loss Bound\n\n")
        f.write(f"- Bound: {b['bound_name']} = {b['direct_tail_hits']}\n")
        f.write(f"- Observed Direct-hit losses: {b['observed_direct_hit_losses']}\n")
        f.write(f"- Bound satisfied: {b['bound_satisfied']}\n")
        if b["bound_violations"]:
            f.write(f"- Bound violations: {json.dumps(b['bound_violations'], ensure_ascii=False)}\n")
        f.write("\n")

        g = audit["claim_gate"]
        f.write("## Claim Gate\n\n")
        f.write(f"- Improvement in hits: {g['improvement_hits']}\n")
        f.write(f"- Passes +2 hits: {g['passes_min_plus_2_hits']}\n")
        f.write(f"- Has expansion-only gains: {g['has_expansion_only_gains']}\n")
        f.write(f"- Parse failures below 2%: {g['parse_failures_below_2_percent']}\n")
        f.write(f"- RCPS improvement paper allowed: {g['rcps_improvement_paper_allowed']}\n\n")

        f.write("## Target-Level Outcomes\n\n")
        f.write("| Target | Outcome | Direct Hit | RCPS Hit | Direct Rank | RCPS Direct Slot | RCPS Expansion Slot |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|\n")
        for row in audit["targets"]:
            f.write(
                f"| {row['target_id']} | {row['paired_outcome']} | {row['direct_hit']} | {row['rcps_hit']} | "
                f"{row['direct_first_rank']} | {row['rcps_direct_slot_hit']} | {row['rcps_expansion_slot_hit']} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit strict Direct-10 vs RCPS comparison")
    parser.add_argument("--direct", default=str(PROJECT_ROOT / "results/direct10_strict_eval_mimo_v25pro.json"))
    parser.add_argument("--rcps", default=str(PROJECT_ROOT / "results/rcps82_strict_eval_mimo_v25pro.json"))
    parser.add_argument("--output-json", default=str(PROJECT_ROOT / "results/rcps_strict_comparison_audit.json"))
    parser.add_argument("--output-md", default=str(PROJECT_ROOT / "results/rcps_strict_comparison_audit.md"))
    parser.add_argument("--k-direct", type=int, default=8)
    args = parser.parse_args()

    direct = load_json(Path(args.direct))
    rcps = load_json(Path(args.rcps))
    audit = compare(direct, rcps, args.k_direct)
    write_json(Path(args.output_json), audit)
    write_markdown(Path(args.output_md), audit)
    print(f"Saved: {args.output_json}")
    print(f"Saved: {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
