#!/usr/bin/env python3
"""
Strict same-contribution judge for ACML RCPS validation.

This script intentionally replaces the permissive "same research direction"
judge used in the stopped RCPS-8/2 exploratory run.

Subcommands:
  calibration     Judge Direct-10 and RCPS-8/2 on a fixed 10-target audit set.
  eval-direct     Judge repaired Direct-10 on any target subset or all targets.
  eval-portfolio  Judge a selected portfolio JSONL on any target subset or all targets.

The judge prompt may see target title/contribution only after final ideas are
selected. Selection/generation are not performed here.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


PROMPT_VERSION = "strict_v2_same_contribution"
PROMPT_CRITERION = (
    "match=true only when the generated idea shares the same central research "
    "problem, same or very close method/mechanism, and same evaluation setting "
    "or intended empirical claim as the target contribution; broad topic "
    "overlap, natural extensions, adjacent follow-up work, applications, or "
    "generic improvements are false."
)

STRICT_JUDGE_PROMPT = """You are judging scientific-idea Hit@10 for a hidden target paper.

Your task is target contribution equivalence, not broad topical relevance.

## Target Paper

Title: {target_title}
Contribution: {target_contribution}

## Generated Idea

Title: {idea_title}
Description: {idea_description}
Key Innovation: {key_innovation}
Addressed Gap: {addressed_gap}

## Strict Match Rule

Return match=true only if the generated idea and target contribution share ALL of:
1. the same central research problem;
2. the same or very close proposed method/mechanism;
3. the same evaluation setting or intended empirical claim.

Return match=false for:
- same broad topic but different contribution;
- natural extensions, applications, robustness additions, efficiency variants, or follow-up work;
- ideas that merely build on, improve, analyze, or apply the target paper;
- overlapping terminology without the same core method and claim.

## Output

Return ONLY this compact JSON object, with a real JSON Boolean:
{{"match": true/false, "confidence": 0.0-1.0, "reason": "brief reason under 25 words"}}

Do not use markdown fences. Do not write any extra text."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open() as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def load_eval_data(path: Path) -> dict[str, dict[str, Any]]:
    records = {}
    for rec in load_jsonl(path):
        records[rec["target_id"]] = rec
    return records


def load_direct_records(path: Path) -> OrderedDict[str, dict[str, Any]]:
    obj = load_json(path)
    records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for rec in obj.get("targets", []):
        records[rec["target_id"]] = rec
    return records


def load_portfolio_records(path: Path) -> OrderedDict[str, dict[str, Any]]:
    records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for rec in load_jsonl(path):
        records[rec["target_id"]] = rec
    return records


def idea_key(idea: dict[str, Any]) -> str:
    payload = {
        "idea_title": idea.get("idea_title", ""),
        "idea_description": idea.get("idea_description", ""),
        "key_innovation": idea.get("key_innovation", ""),
        "addressed_gap": idea.get("addressed_gap", ""),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def clean_idea_for_output(idea: dict[str, Any]) -> dict[str, Any]:
    keep = ["idea_title", "idea_description", "key_innovation", "addressed_gap", "candidate_id", "batch", "slot_source"]
    return {k: idea[k] for k in keep if k in idea}


def parse_strict_json(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {
            "match": False,
            "confidence": 0.0,
            "reason": "",
            "parsed_response": None,
            "parse_status": "empty_response",
        }

    raw_clean = raw.strip()
    if not raw_clean:
        return {
            "match": False,
            "confidence": 0.0,
            "reason": "",
            "parsed_response": None,
            "parse_status": "empty_response",
        }

    try:
        parsed = json.loads(raw_clean)
    except json.JSONDecodeError:
        return {
            "match": False,
            "confidence": 0.0,
            "reason": "",
            "parsed_response": None,
            "parse_status": "json_error_or_extra_text",
        }

    if not isinstance(parsed, dict):
        return {
            "match": False,
            "confidence": 0.0,
            "reason": "",
            "parsed_response": parsed,
            "parse_status": "not_dict",
        }

    match_value = parsed.get("match")
    if not isinstance(match_value, bool):
        return {
            "match": False,
            "confidence": 0.0,
            "reason": str(parsed.get("reason", ""))[:240],
            "parsed_response": parsed,
            "parse_status": "invalid_match_type",
        }

    confidence_value = parsed.get("confidence", 0.0)
    if not isinstance(confidence_value, (int, float)):
        return {
            "match": False,
            "confidence": 0.0,
            "reason": str(parsed.get("reason", ""))[:240],
            "parsed_response": parsed,
            "parse_status": "invalid_confidence_type",
        }

    confidence = float(confidence_value)
    if confidence < 0.0 or confidence > 1.0:
        return {
            "match": False,
            "confidence": confidence,
            "reason": str(parsed.get("reason", ""))[:240],
            "parsed_response": parsed,
            "parse_status": "confidence_out_of_range",
        }

    return {
        "match": match_value,
        "confidence": confidence,
        "reason": str(parsed.get("reason", ""))[:240],
        "parsed_response": parsed,
        "parse_status": "ok",
    }


def judge_idea(
    idea: dict[str, Any],
    target_title: str,
    target_contribution: str,
    model: str,
    sleep_seconds: float,
    max_tokens: int,
) -> dict[str, Any]:
    from mimo_client import chat_completion

    prompt = STRICT_JUDGE_PROMPT.format(
        target_title=target_title,
        target_contribution=target_contribution,
        idea_title=idea.get("idea_title", ""),
        idea_description=idea.get("idea_description", ""),
        key_innovation=idea.get("key_innovation", ""),
        addressed_gap=idea.get("addressed_gap", ""),
    )

    result = chat_completion(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
        sleep_seconds=sleep_seconds,
    )

    raw = result.get("content") or ""
    parsed = parse_strict_json(raw)
    parsed.update(
        {
            "raw_response": raw,
            "finish_reason": result.get("finish_reason"),
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "total_tokens": result.get("total_tokens"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "prompt_version": PROMPT_VERSION,
            "criterion": PROMPT_CRITERION,
        }
    )
    return parsed


def target_metadata(target_id: str, eval_data: dict[str, dict[str, Any]], fallback_title: str = "") -> tuple[str, str, str]:
    rec = eval_data.get(target_id, {})
    title = rec.get("title") or fallback_title
    contribution = rec.get("contribution") or title
    source = rec.get("contribution_source", "")
    return title, contribution, source


def summarize_judgments(judgments: list[dict[str, Any]]) -> dict[str, Any]:
    parse_ok = sum(1 for j in judgments if j.get("parse_status") == "ok")
    parse_fail = len(judgments) - parse_ok
    hits = sum(1 for j in judgments if j.get("match") is True)
    return {
        "num_judgments": len(judgments),
        "parse_ok": parse_ok,
        "parse_fail": parse_fail,
        "parse_rate": round(parse_ok / max(len(judgments), 1) * 100, 1),
        "idea_matches": hits,
    }


def build_eval_checkpoint(
    method: str,
    model: str,
    input_data: str,
    eval_data_name: str,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    all_judgments = [j for t in targets for j in t.get("judgments", [])]
    summary = summarize_judgments(all_judgments)
    hits = sum(1 for t in targets if t.get("hit"))
    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "method": method,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "criterion": PROMPT_CRITERION,
        "eval_data": eval_data_name,
        "input_data": input_data,
        "total_targets": len(targets),
        "completed": len(targets),
        "hits": hits,
        "hit_at_10": round(hits / max(len(targets), 1) * 100, 1),
        "parse_ok": summary["parse_ok"],
        "parse_fail": summary["parse_fail"],
        "parse_rate": summary["parse_rate"],
        "total_input_tokens": sum(j.get("input_tokens") or 0 for j in all_judgments),
        "total_output_tokens": sum(j.get("output_tokens") or 0 for j in all_judgments),
        "total_tokens": sum(j.get("total_tokens") or 0 for j in all_judgments),
        "targets": targets,
    }


def evaluate_ideas_for_target(
    target_id: str,
    target_title: str,
    target_contribution: str,
    ideas: list[dict[str, Any]],
    model: str,
    sleep_seconds: float,
    max_tokens: int,
    dry_run: bool,
) -> list[dict[str, Any]]:
    judgments = []
    for idea_idx, idea in enumerate(ideas):
        if dry_run:
            judgment = {
                "match": False,
                "confidence": 0.0,
                "reason": "dry run",
                "raw_response": "",
                "parsed_response": None,
                "parse_status": "dry_run",
                "prompt_version": PROMPT_VERSION,
                "criterion": PROMPT_CRITERION,
            }
        else:
            judgment = judge_idea(
                idea=idea,
                target_title=target_title,
                target_contribution=target_contribution,
                model=model,
                sleep_seconds=sleep_seconds,
                max_tokens=max_tokens,
            )
        judgment["idea_index"] = idea_idx
        judgment["idea_title"] = idea.get("idea_title", "")
        judgment["slot_source"] = idea.get("slot_source", "direct")
        judgments.append(judgment)
    return judgments


def evaluate_method_records(
    records: OrderedDict[str, dict[str, Any]],
    eval_data: dict[str, dict[str, Any]],
    method: str,
    input_label: str,
    idea_field: str,
    target_ids: list[str] | None,
    output_path: Path,
    model: str,
    sleep_seconds: float,
    max_tokens: int,
    dry_run: bool,
    overwrite: bool,
) -> dict[str, Any]:
    if output_path.exists() and not overwrite and not dry_run:
        raise FileExistsError(f"Output exists; pass --overwrite to replace: {output_path}")

    selected_ids = target_ids or list(records.keys())
    missing = [tid for tid in selected_ids if tid not in records]
    if missing:
        raise KeyError(f"{len(missing)} target IDs missing from {input_label}: {missing[:5]}")

    output_targets: list[dict[str, Any]] = []
    for idx, target_id in enumerate(selected_ids):
        rec = records[target_id]
        fallback_title = rec.get("target_title", "")
        title, contribution, contribution_source = target_metadata(target_id, eval_data, fallback_title)
        ideas = rec.get(idea_field, [])
        if len(ideas) != 10:
            print(f"WARNING: {target_id} has {len(ideas)} ideas for {method}", file=sys.stderr)

        print(f"[{idx + 1}/{len(selected_ids)}] {method} {target_id}: {title[:80]} ({len(ideas)} ideas)")
        judgments = evaluate_ideas_for_target(
            target_id=target_id,
            target_title=title,
            target_contribution=contribution,
            ideas=ideas,
            model=model,
            sleep_seconds=sleep_seconds,
            max_tokens=max_tokens,
            dry_run=dry_run,
        )

        hit = any(j.get("parse_status") == "ok" and j.get("match") is True for j in judgments)
        output_targets.append(
            {
                "target_id": target_id,
                "target_title": title,
                "target_contribution": contribution,
                "contribution_source": contribution_source,
                "num_selected": len(ideas),
                "direct_slots": sum(1 for s in ideas if s.get("slot_source", "direct") == "direct"),
                "expansion_slots": sum(1 for s in ideas if str(s.get("slot_source", "")).startswith("expansion")),
                "selected_ideas": [clean_idea_for_output(i) for i in ideas],
                "judgments": judgments,
                "hit": hit,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if not dry_run:
            checkpoint = build_eval_checkpoint(
                method=method,
                model=model,
                input_data=input_label,
                eval_data_name="eval_neurips_2025_oral_enriched.jsonl",
                targets=output_targets,
            )
            write_json(output_path, checkpoint)

    result = build_eval_checkpoint(
        method=method,
        model=model,
        input_data=input_label,
        eval_data_name="eval_neurips_2025_oral_enriched.jsonl",
        targets=output_targets,
    )
    if not dry_run:
        write_json(output_path, result)
        print(f"Saved: {output_path}")
    else:
        print("Dry run complete; no MiMo calls and no output written.")
    return result


def choose_calibration_targets(
    rcps_checkpoint_path: Path,
    judge_audit_path: Path,
    n_checkpoint: int = 5,
    n_disagreement: int = 5,
) -> list[dict[str, str]]:
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()

    if rcps_checkpoint_path.exists():
        rcps = load_json(rcps_checkpoint_path)
        for rec in rcps.get("targets", [])[:n_checkpoint]:
            target_id = rec["target_id"]
            chosen.append({"target_id": target_id, "source": "stopped_rcps_checkpoint_first5"})
            seen.add(target_id)

    if judge_audit_path.exists():
        audit = load_json(judge_audit_path)
        preferred_categories = {"bcs_only", "both_miss", "overlap"}
        rows = audit.get("results", [])
        rows = sorted(
            rows,
            key=lambda r: (
                0 if r.get("category") in preferred_categories else 1,
                0 if any(j.get("label_changed") for j in r.get("judgments", [])) else 1,
                r.get("target_id", ""),
            ),
        )
        for rec in rows:
            target_id = rec["target_id"]
            if target_id in seen:
                continue
            if rec.get("category") not in preferred_categories and len(chosen) >= n_checkpoint + n_disagreement:
                continue
            chosen.append({"target_id": target_id, "source": f"judge_format_audit_{rec.get('category', 'unknown')}"})
            seen.add(target_id)
            if len(chosen) >= n_checkpoint + n_disagreement:
                break

    if len(chosen) < n_checkpoint + n_disagreement:
        raise RuntimeError(
            f"Only selected {len(chosen)} calibration targets; expected {n_checkpoint + n_disagreement}"
        )

    return chosen[: n_checkpoint + n_disagreement]


def evaluate_calibration(
    direct_records: OrderedDict[str, dict[str, Any]],
    portfolio_records: OrderedDict[str, dict[str, Any]],
    eval_data: dict[str, dict[str, Any]],
    target_plan: list[dict[str, str]],
    output_json: Path,
    output_md: Path,
    model: str,
    sleep_seconds: float,
    max_tokens: int,
    dry_run: bool,
    overwrite: bool,
) -> dict[str, Any]:
    if (output_json.exists() or output_md.exists()) and not overwrite and not dry_run:
        raise FileExistsError("Calibration output exists; pass --overwrite to replace.")

    targets_out = []
    total_unique_calls = 0

    for idx, item in enumerate(target_plan):
        target_id = item["target_id"]
        if target_id not in direct_records:
            raise KeyError(f"Missing Direct-10 target: {target_id}")
        if target_id not in portfolio_records:
            raise KeyError(f"Missing RCPS portfolio target: {target_id}")

        direct_ideas = direct_records[target_id].get("generated_ideas", [])
        rcps_ideas = portfolio_records[target_id].get("selected", [])
        fallback_title = direct_records[target_id].get("target_title", portfolio_records[target_id].get("target_title", ""))
        title, contribution, contribution_source = target_metadata(target_id, eval_data, fallback_title)

        print(f"[{idx + 1}/{len(target_plan)}] calibration {target_id}: {title[:80]}")

        unique_ideas: OrderedDict[str, dict[str, Any]] = OrderedDict()
        method_refs: dict[str, list[dict[str, Any]]] = {"direct10": [], "rcps82": []}

        for idea_idx, idea in enumerate(direct_ideas):
            key = idea_key(idea)
            unique_ideas.setdefault(key, idea)
            method_refs["direct10"].append({"key": key, "idea_index": idea_idx, "slot_source": "direct"})

        for idea_idx, idea in enumerate(rcps_ideas):
            key = idea_key(idea)
            unique_ideas.setdefault(key, idea)
            method_refs["rcps82"].append(
                {"key": key, "idea_index": idea_idx, "slot_source": idea.get("slot_source", "unknown")}
            )

        judged_by_key: dict[str, dict[str, Any]] = {}
        for key_idx, (key, idea) in enumerate(unique_ideas.items()):
            print(f"  unique idea {key_idx + 1}/{len(unique_ideas)}")
            if dry_run:
                judgment = {
                    "match": False,
                    "confidence": 0.0,
                    "reason": "dry run",
                    "raw_response": "",
                    "parsed_response": None,
                    "parse_status": "dry_run",
                    "prompt_version": PROMPT_VERSION,
                    "criterion": PROMPT_CRITERION,
                }
            else:
                judgment = judge_idea(
                    idea=idea,
                    target_title=title,
                    target_contribution=contribution,
                    model=model,
                    sleep_seconds=sleep_seconds,
                    max_tokens=max_tokens,
                )
            judgment["idea_title"] = idea.get("idea_title", "")
            judged_by_key[key] = judgment
            total_unique_calls += 1

        method_outputs = {}
        for method_name, refs in method_refs.items():
            judgments = []
            ideas = direct_ideas if method_name == "direct10" else rcps_ideas
            for ref in refs:
                base = dict(judged_by_key[ref["key"]])
                base["idea_index"] = ref["idea_index"]
                base["slot_source"] = ref["slot_source"]
                judgments.append(base)
            method_outputs[method_name] = {
                "num_selected": len(ideas),
                "selected_ideas": [clean_idea_for_output(i) for i in ideas],
                "judgments": judgments,
                "hit": any(j.get("parse_status") == "ok" and j.get("match") is True for j in judgments),
            }

        targets_out.append(
            {
                "target_id": target_id,
                "selection_source": item["source"],
                "target_title": title,
                "target_contribution": contribution,
                "contribution_source": contribution_source,
                "unique_idea_calls": len(unique_ideas),
                "methods": method_outputs,
            }
        )

        if not dry_run:
            partial = build_calibration_output(model, target_plan, targets_out, total_unique_calls)
            write_json(output_json, partial)
            write_calibration_markdown(output_md, partial)

    result = build_calibration_output(model, target_plan, targets_out, total_unique_calls)
    if not dry_run:
        write_json(output_json, result)
        write_calibration_markdown(output_md, result)
        print(f"Saved: {output_json}")
        print(f"Saved: {output_md}")
    else:
        print("Dry run complete; no MiMo calls and no output written.")
    return result


def build_calibration_output(
    model: str,
    target_plan: list[dict[str, str]],
    targets: list[dict[str, Any]],
    unique_calls: int,
) -> dict[str, Any]:
    method_summaries: dict[str, dict[str, Any]] = {}
    for method_name in ["direct10", "rcps82"]:
        method_targets = [t["methods"][method_name] for t in targets]
        hits = sum(1 for t in method_targets if t.get("hit"))
        judgments = [j for t in method_targets for j in t.get("judgments", [])]
        summary = summarize_judgments(judgments)
        method_summaries[method_name] = {
            "completed": len(method_targets),
            "hits": hits,
            "hit_at_10": round(hits / max(len(method_targets), 1) * 100, 1),
            **summary,
        }

    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "kind": "strict_judge_calibration",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "criterion": PROMPT_CRITERION,
        "target_plan": target_plan,
        "unique_mimo_calls": unique_calls,
        "method_summaries": method_summaries,
        "targets": targets,
    }


def write_calibration_markdown(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# Strict Judge Calibration Audit\n\n")
        f.write(f"Generated: {obj['timestamp']}\n\n")
        f.write(f"- Prompt version: `{obj['prompt_version']}`\n")
        f.write(f"- Unique MiMo calls: {obj['unique_mimo_calls']}\n")
        f.write(f"- Criterion: {obj['criterion']}\n\n")

        f.write("## Method Summary\n\n")
        f.write("| Method | Targets | Hits | Hit@10 | Parse OK | Parse Fail |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for method_name, summary in obj["method_summaries"].items():
            f.write(
                f"| {method_name} | {summary['completed']} | {summary['hits']} | "
                f"{summary['hit_at_10']}% | {summary['parse_ok']} | {summary['parse_fail']} |\n"
            )
        f.write("\n")

        f.write("## Matched Ideas\n\n")
        for target in obj["targets"]:
            f.write(f"### {target['target_id']} — {target['target_title']}\n\n")
            f.write(f"- Source: {target['selection_source']}\n")
            for method_name, method in target["methods"].items():
                f.write(f"- {method_name}: {'HIT' if method.get('hit') else 'MISS'}\n")
                matches = [j for j in method.get("judgments", []) if j.get("parse_status") == "ok" and j.get("match") is True]
                if not matches:
                    f.write("  - No strict matches.\n")
                for j in matches:
                    title = j.get("idea_title", "")
                    f.write(
                        f"  - idx={j.get('idea_index')} source={j.get('slot_source')} "
                        f"conf={j.get('confidence')}: {title}\n"
                    )
                    f.write(f"    - reason: {j.get('reason', '')}\n")
            f.write("\n")


def parse_target_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    path = Path(value)
    if path.exists():
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return [part.strip() for part in value.split(",") if part.strip()]


def validate_common_args(args: argparse.Namespace) -> None:
    if args.sleep_seconds < 0.5:
        raise ValueError("--sleep-seconds must be at least 0.5")
    if args.max_tokens < 512:
        raise ValueError("--max-tokens should be at least 512 for MiMo reasoning-token responses")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data/scireasoning/eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--dry-run", action="store_true", help="Load inputs and print plan without MiMo calls or output writes.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict same-contribution judge for RCPS validation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    calibration = subparsers.add_parser("calibration", help="Run the 10-target strict judge calibration")
    add_common_args(calibration)
    calibration.add_argument("--direct", default=str(PROJECT_ROOT / "results/direct10_complete_mimo_v25pro.json"))
    calibration.add_argument("--portfolio", default=str(PROJECT_ROOT / "results/rcps82_selected_mimo_v25pro.jsonl"))
    calibration.add_argument("--rcps-checkpoint", default=str(PROJECT_ROOT / "results/rcps82_eval_mimo_v25pro.json"))
    calibration.add_argument("--judge-audit", default=str(PROJECT_ROOT / "results/judge_format_audit.json"))
    calibration.add_argument("--output-json", default=str(PROJECT_ROOT / "results/strict_judge_calibration_10targets.json"))
    calibration.add_argument("--output-md", default=str(PROJECT_ROOT / "results/strict_judge_calibration_10targets.md"))

    eval_direct = subparsers.add_parser("eval-direct", help="Strictly judge repaired Direct-10")
    add_common_args(eval_direct)
    eval_direct.add_argument("--direct", default=str(PROJECT_ROOT / "results/direct10_complete_mimo_v25pro.json"))
    eval_direct.add_argument("--output", default=str(PROJECT_ROOT / "results/direct10_strict_eval_mimo_v25pro.json"))
    eval_direct.add_argument("--target-ids", default=None, help="Comma list or newline file. Default: all targets.")

    eval_portfolio = subparsers.add_parser("eval-portfolio", help="Strictly judge a selected portfolio JSONL")
    add_common_args(eval_portfolio)
    eval_portfolio.add_argument("--method", required=True)
    eval_portfolio.add_argument("--portfolio", required=True)
    eval_portfolio.add_argument("--output", required=True)
    eval_portfolio.add_argument("--target-ids", default=None, help="Comma list or newline file. Default: all targets.")

    args = parser.parse_args()
    validate_common_args(args)

    eval_data = load_eval_data(Path(args.eval_data))

    if args.command == "calibration":
        direct_records = load_direct_records(Path(args.direct))
        portfolio_records = load_portfolio_records(Path(args.portfolio))
        target_plan = choose_calibration_targets(Path(args.rcps_checkpoint), Path(args.judge_audit))
        print("Calibration targets:")
        for item in target_plan:
            print(f"  {item['target_id']} ({item['source']})")
        evaluate_calibration(
            direct_records=direct_records,
            portfolio_records=portfolio_records,
            eval_data=eval_data,
            target_plan=target_plan,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            model=args.model,
            sleep_seconds=args.sleep_seconds,
            max_tokens=args.max_tokens,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    elif args.command == "eval-direct":
        direct_records = load_direct_records(Path(args.direct))
        evaluate_method_records(
            records=direct_records,
            eval_data=eval_data,
            method="direct10_strict",
            input_label=Path(args.direct).name,
            idea_field="generated_ideas",
            target_ids=parse_target_ids(args.target_ids),
            output_path=Path(args.output),
            model=args.model,
            sleep_seconds=args.sleep_seconds,
            max_tokens=args.max_tokens,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    elif args.command == "eval-portfolio":
        portfolio_records = load_portfolio_records(Path(args.portfolio))
        evaluate_method_records(
            records=portfolio_records,
            eval_data=eval_data,
            method=args.method,
            input_label=Path(args.portfolio).name,
            idea_field="selected",
            target_ids=parse_target_ids(args.target_ids),
            output_path=Path(args.output),
            model=args.model,
            sleep_seconds=args.sleep_seconds,
            max_tokens=args.max_tokens,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    else:
        parser.error(f"Unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted; partial checkpoint may have been written.", file=sys.stderr)
        raise
