#!/usr/bin/env python3
"""
Rejudge fixed final-idea sets with MiMo or SJTU-hosted judges.

This script makes no generation calls. It is used to separate judge/script
effects from generator effects:

  H(source final ideas, judge model)

Supported fixed sources:
- direct10_mimo_submitted: results/direct10_complete_mimo_v25pro.json
- bcs50_mimo_submitted: results/bcs50_eval_mimo_v25pro.json
- pgcr_mimo_submitted: results/pgcr_enriched_eval.json
- clean_direct10_generation: any clean generation artifact with generated_ideas
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "results" / "experiments" / "20260614_multimodel_matrix"
DEFAULT_EVAL_DATA = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"

SOURCE_DEFAULTS = {
    "direct10_mimo_submitted": PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json",
    "bcs50_mimo_submitted": PROJECT_ROOT / "results" / "bcs50_eval_mimo_v25pro.json",
    "pgcr_mimo_submitted": PROJECT_ROOT / "results" / "pgcr_enriched_eval.json",
}

SOURCE_IDEA_FIELDS = {
    "direct10_mimo_submitted": "generated_ideas",
    "bcs50_mimo_submitted": "selected_ideas",
    "pgcr_mimo_submitted": "selected_ideas",
    "clean_direct10_generation": "generated_ideas",
}

JUDGE_PROMPT = """You are an expert AI research evaluator. Determine whether a generated research idea is a semantic match for a target published paper.

## Target Paper

**Title:** {target_title}
**Contribution:** {target_contribution}

## Generated Idea

**Title:** {idea_title}
**Description:** {idea_description}
**Key Innovation:** {key_innovation}
**Addressed Gap:** {addressed_gap}

## Task

Determine if this generated idea captures the same core research direction as the target paper. Consider:
- Is the core problem/approach similar?
- Would a researcher reading both recognize them as the same research direction?
- Ignore superficial wording differences; focus on semantic overlap.

## Output Format

Return a JSON object with:
- "match": true or false
- "confidence": a number from 0.0 to 1.0
- "reason": a brief explanation of your judgment

Return ONLY the JSON object, no other text."""


def safe_model_slug(model_id: str) -> str:
    return model_id.lower().replace("/", "-").replace("_", "-").replace(".", "")


def parse_json_from_response(text: str):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()

    fixed = re.sub(r",\s*\}", "}", text)
    fixed = re.sub(r",\s*\]", "]", fixed)
    for candidate in [text, fixed]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{[\s\S]*\}", fixed)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            recovered = recover_quasi_json_judgment(match.group())
            if recovered is not None:
                return recovered
            return None
    return recover_quasi_json_judgment(fixed)


def recover_quasi_json_judgment(text: str):
    """Recover MiMo judge outputs with parseable match/confidence but malformed reason."""
    text = (text or "").strip()
    match_field = re.search(r'"match"\s*:\s*(true|false)\b', text, flags=re.IGNORECASE)
    confidence_field = re.search(r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    if not match_field or not confidence_field:
        return None

    reason = ""
    reason_field = re.search(r'"reason"\s*:\s*([\s\S]*?)\s*\}\s*$', text)
    if reason_field:
        reason = reason_field.group(1).strip()
        reason = re.sub(r",\s*$", "", reason).strip()
        if reason.startswith('"'):
            try:
                reason = json.loads(reason)
            except json.JSONDecodeError:
                reason = reason.strip('"')
        elif reason.endswith('"'):
            reason = reason[:-1]
        reason = str(reason).strip()

    return {
        "match": match_field.group(1).lower() == "true",
        "confidence": float(confidence_field.group(1)),
        "reason": reason,
        "_recovered_parse": True,
    }


def apply_parsed_judgment(judgment: dict, parsed: dict) -> bool:
    match_val = parsed.get("match")
    if not isinstance(match_val, bool):
        return False
    judgment["match"] = match_val
    judgment["confidence"] = float(parsed.get("confidence", 0.0) or 0.0)
    judgment["reason"] = str(parsed.get("reason", ""))[:1000]
    judgment["parse_status"] = "ok"
    if parsed.get("_recovered_parse"):
        judgment["recovered_parse"] = True
    return True


def recompute_metrics(records: list[dict]) -> dict:
    parse_status = Counter()
    hits = 0
    input_tokens = 0
    output_tokens = 0
    judgments = 0
    recovered = 0
    for record in records:
        hit = False
        for judgment in record.get("judgments", []):
            judgments += 1
            parse_status[judgment.get("parse_status", "missing")] += 1
            input_tokens += judgment.get("input_tokens") or 0
            output_tokens += judgment.get("output_tokens") or 0
            if judgment.get("recovered_parse") is True:
                recovered += 1
            if judgment.get("match") is True:
                hit = True
        record["hit"] = hit
        if hit:
            hits += 1
    ok = parse_status.get("ok", 0)
    fail = judgments - ok
    return {
        "hits": hits,
        "hit_at_10": round(hits / max(len(records), 1) * 100, 1),
        "judge_parse_ok": ok,
        "judge_parse_fail": fail,
        "judge_parse_rate": round(ok / max(judgments, 1) * 100, 1),
        "judge_parse_recovered": recovered,
        "parse_status_counts": dict(parse_status),
        "judge_total_input_tokens": input_tokens,
        "judge_total_output_tokens": output_tokens,
        "judge_total_tokens": input_tokens + output_tokens,
        "total_judgments": judgments,
    }


def repair_existing_artifact(output_path: Path) -> int:
    if not output_path.exists():
        print(f"Repair input not found: {output_path}")
        return 1

    output = json.loads(output_path.read_text())
    repaired = 0
    still_failed = 0
    for record in output.get("targets", []):
        for judgment in record.get("judgments", []):
            if judgment.get("parse_status") == "ok":
                continue
            raw = judgment.get("raw_response", "")
            parsed = parse_json_from_response(raw)
            if isinstance(parsed, dict) and apply_parsed_judgment(judgment, parsed):
                repaired += 1
            elif not raw:
                judgment["parse_status"] = "empty_response"
                still_failed += 1
            else:
                still_failed += 1

    records = output.get("targets", [])
    metrics = recompute_metrics(records)
    output.update(
        {
            "completed": len(records),
            "all_complete": len(records) == output.get("total_targets") and metrics["total_judgments"] == output.get("expected_judgments"),
            **metrics,
            "repair_metadata": {
                "timestamp": datetime.now().isoformat(),
                "mode": "local_raw_response_reparse",
                "repaired_judgments": repaired,
                "still_failed_judgments": still_failed,
            },
        }
    )
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"Repaired judgments: {repaired}")
    print(f"Still failed judgments: {still_failed}")
    print(f"Parse: {metrics['judge_parse_ok']}/{metrics['total_judgments']} ({metrics['judge_parse_rate']}%)")
    print(f"Hits: {metrics['hits']}/{len(records)} ({metrics['hit_at_10']}%)")
    print(f"Output: {output_path}")
    return 0


def load_sjtu_chat_completion():
    spec = importlib.util.spec_from_file_location(
        "openai_compatible_client",
        PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.chat_completion


def load_mimo_chat_completion():
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from mimo_client import chat_completion

    return chat_completion


def call_chat(provider: str, model: str, messages: list[dict], sleep_seconds: float, max_tokens: int) -> dict:
    if provider == "sjtu":
        return load_sjtu_chat_completion()(
            messages,
            model=model,
            provider="sjtu",
            temperature=0.0,
            max_tokens=max_tokens,
            sleep_seconds=sleep_seconds,
        )
    if provider == "mimo":
        return load_mimo_chat_completion()(
            messages,
            model=model,
            temperature=0.0,
            max_tokens=max_tokens,
            sleep_seconds=sleep_seconds,
        )
    raise ValueError(f"Unknown provider: {provider}")


def load_eval_data(path: Path) -> dict:
    records = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                records[rec["target_id"]] = rec
    return records


def load_source_targets(source: str, input_path: Path | None, eval_data: dict) -> tuple[list[dict], dict]:
    if source != "clean_direct10_generation":
        path = input_path or SOURCE_DEFAULTS[source]
        obj = json.loads(path.read_text())
        idea_field = SOURCE_IDEA_FIELDS[source]
        targets = []
        for record in obj.get("targets", []):
            target_id = record.get("target_id")
            eval_rec = eval_data.get(target_id, {})
            targets.append(
                {
                    "target_id": target_id,
                    "ideas": record.get(idea_field, []),
                    "source_metadata": {
                        "idea_field": idea_field,
                        "num_candidates": record.get("num_candidates"),
                        "num_selected": record.get("num_selected"),
                        "original_hit": record.get("hit"),
                    },
                    "target_title": eval_rec.get("title", record.get("target_title", "")),
                    "target_contribution": eval_rec.get("contribution", record.get("target_contribution", "")),
                }
            )
        meta = {
            "source": source,
            "source_file": str(path.relative_to(PROJECT_ROOT)),
            "source_method": obj.get("method", source),
            "source_model": obj.get("model") or obj.get("generator_model") or obj.get("judge_model"),
        }
        return targets, meta

    if input_path is None:
        raise ValueError("--input is required for clean_direct10_generation")
    obj = json.loads(input_path.read_text())
    targets = []
    for record in obj.get("targets", []):
        target_id = record.get("target_id")
        eval_rec = eval_data.get(target_id, {})
        targets.append(
            {
                "target_id": target_id,
                "ideas": record.get("generated_ideas", []),
                "source_metadata": {
                    "idea_field": "generated_ideas",
                    "generation_parse_status": record.get("generation", {}).get("parse_status"),
                    "target_visible_metadata_stored": record.get("target_visible_metadata_stored"),
                },
                "target_title": eval_rec.get("title", ""),
                "target_contribution": eval_rec.get("contribution", ""),
            }
        )
    meta = {
        "source": source,
        "source_file": str(input_path.relative_to(PROJECT_ROOT)) if input_path.is_relative_to(PROJECT_ROOT) else str(input_path),
        "source_method": obj.get("kind", source),
        "source_model": obj.get("generator_model"),
        "context_mode": obj.get("context_mode"),
        "any_leakage_detected": obj.get("any_leakage_detected"),
    }
    return targets, meta


def validate_targets(targets: list[dict], expected: int | None) -> list[str]:
    issues = []
    if expected is not None and len(targets) != expected:
        issues.append(f"target_count_expected_{expected}_found_{len(targets)}")
    seen = set()
    for target in targets:
        target_id = target.get("target_id")
        if not target_id:
            issues.append("missing_target_id")
            continue
        if target_id in seen:
            issues.append(f"duplicate_target:{target_id}")
        seen.add(target_id)
        if not target.get("target_title"):
            issues.append(f"missing_target_title:{target_id}")
        if not target.get("target_contribution"):
            issues.append(f"missing_target_contribution:{target_id}")
        if len(target.get("ideas", [])) != 10:
            issues.append(f"idea_count_not_10:{target_id}:{len(target.get('ideas', []))}")
    return issues


def judge_idea(provider: str, model: str, sleep_seconds: float, max_tokens: int, idea: dict, target_title: str, target_contribution: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        target_title=target_title,
        target_contribution=target_contribution,
        idea_title=idea.get("idea_title", ""),
        idea_description=idea.get("idea_description", ""),
        key_innovation=idea.get("key_innovation", ""),
        addressed_gap=idea.get("addressed_gap", ""),
    )
    try:
        result = call_chat(provider, model, [{"role": "user", "content": prompt}], sleep_seconds, max_tokens)
    except Exception as exc:
        return {
            "match": False,
            "confidence": 0.0,
            "reason": str(exc)[:500],
            "raw_response": "",
            "parse_status": "api_error",
            "input_tokens": None,
            "output_tokens": None,
            "finish_reason": None,
        }

    raw = result.get("content", "")
    parsed = parse_json_from_response(raw)
    judgment = {
        "match": False,
        "confidence": 0.0,
        "reason": "",
        "raw_response": raw,
        "parse_status": "json_error",
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "finish_reason": result.get("finish_reason"),
    }
    if isinstance(parsed, dict):
        if apply_parsed_judgment(judgment, parsed):
            pass
        elif isinstance(parsed.get("match"), str):
            judgment["parse_status"] = "string_boolean"
            judgment["reason"] = str(parsed.get("reason", ""))[:1000]
        else:
            judgment["parse_status"] = "invalid_match_type"
            judgment["reason"] = str(parsed.get("reason", ""))[:1000]
    elif not raw:
        judgment["parse_status"] = "empty_response"
    return judgment


def main() -> int:
    parser = argparse.ArgumentParser(description="Rejudge fixed final ideas with a selected judge")
    parser.add_argument("--source", required=True, choices=sorted(SOURCE_IDEA_FIELDS))
    parser.add_argument("--input", help="Input artifact for clean_direct10_generation or override source default")
    parser.add_argument("--eval-data", default=str(DEFAULT_EVAL_DATA))
    parser.add_argument("--judge-provider", required=True, choices=["mimo", "sjtu"])
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--output")
    parser.add_argument("--output-dir", default=str(EXP_DIR))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repair-existing-only", action="store_true", help="Repair parse statuses from stored raw_response without API calls")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else None
    eval_data = load_eval_data(Path(args.eval_data))
    targets, source_meta = load_source_targets(args.source, input_path, eval_data)
    if args.limit:
        targets = targets[: args.limit]

    issues = validate_targets(targets, args.limit or 77)
    judge_slug = f"{args.judge_provider}-{safe_model_slug(args.judge_model)}"
    source_slug = args.source
    if args.source == "clean_direct10_generation":
        source_model = source_meta.get("source_model") or "unknown-generator"
        source_slug = f"clean_direct10_{safe_model_slug(source_model)}"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scope = f"{len(targets)}t"
    output_path = Path(args.output) if args.output else output_dir / f"rejudge_fixed_{source_slug}_{judge_slug}_{scope}_20260614.json"

    print(f"Source: {args.source}")
    print(f"Source file: {source_meta.get('source_file')}")
    print(f"Targets: {len(targets)}")
    print(f"Judge: {args.judge_provider}/{args.judge_model}")
    print(f"Output: {output_path}")

    if issues:
        print("INPUT INVALID:")
        for issue in issues[:80]:
            print(f"  - {issue}")
        return 1

    if args.repair_existing_only:
        return repair_existing_artifact(output_path)

    if args.dry_run:
        print("Dry run complete; no API calls made.")
        for target in targets[:3]:
            print(f"  {target['target_id']}: {len(target['ideas'])} fixed ideas")
        return 0

    results = []
    completed_ids = set()
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text())
        seen = set()
        dropped = 0
        for record in existing.get("targets", []):
            target_id = record.get("target_id")
            judgments = record.get("judgments", [])
            parse_complete = len(judgments) == 10 and all(j.get("parse_status") == "ok" for j in judgments)
            if not target_id or target_id in seen or not parse_complete:
                dropped += 1
                continue
            results.append(record)
            seen.add(target_id)
        completed_ids = seen
        print(f"Resuming: {len(completed_ids)} complete targets")
        if dropped:
            print(f"Dropped {dropped} incomplete/duplicate records")

    def recompute():
        return recompute_metrics(results)

    def write_checkpoint():
        metrics = recompute()
        output = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "kind": "rejudge_fixed_final_ideas",
            "source": args.source,
            "source_metadata": source_meta,
            "judge_provider": args.judge_provider,
            "judge_model": args.judge_model,
            "prompt_version": "same_core_research_direction_enriched_v1",
            "total_targets": len(targets),
            "completed": len(results),
            "expected_judgments": len(targets) * 10,
            "all_complete": len(results) == len(targets) and metrics["total_judgments"] == len(targets) * 10,
            **metrics,
            "targets": results,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    remaining = [target for target in targets if target["target_id"] not in completed_ids]
    for idx, target in enumerate(remaining, 1):
        print(f"\n[{idx}/{len(remaining)}] {target['target_id']}: {target['target_title'][:70]}...")
        judgments = []
        hit = False
        for idea_idx, idea in enumerate(target["ideas"]):
            judgment = judge_idea(
                args.judge_provider,
                args.judge_model,
                args.sleep_seconds,
                args.max_tokens,
                idea,
                target["target_title"],
                target["target_contribution"],
            )
            judgment["idea_index"] = idea_idx
            judgments.append(judgment)
            if judgment.get("match") is True:
                hit = True
                print(f"  Idea {idea_idx + 1}: MATCH")
            elif judgment.get("parse_status") != "ok":
                print(f"  Idea {idea_idx + 1}: {judgment.get('parse_status')}")

        results.append(
            {
                "target_id": target["target_id"],
                "target_title": target["target_title"],
                "target_contribution": target["target_contribution"],
                "source_metadata": target["source_metadata"],
                "final_ideas": target["ideas"],
                "judgments": judgments,
                "hit": hit,
                "timestamp": datetime.now().isoformat(),
            }
        )
        write_checkpoint()
        print(f"  {'HIT' if hit else 'MISS'}; checkpoint saved")

    write_checkpoint()
    metrics = recompute()
    print("\nComplete")
    print(f"Hits: {metrics['hits']}/{len(results)} ({metrics['hit_at_10']}%)")
    print(f"Parse: {metrics['judge_parse_ok']}/{metrics['total_judgments']} ({metrics['judge_parse_rate']}%)")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
