#!/usr/bin/env python3
"""
Evaluate clean-context Direct-10 generations with a ZhiYuan/OpenAI-compatible judge.

This script judges a fixed generation artifact. It does not generate ideas.
Generation remains target-hidden; the judge sees target title and enriched
contribution only after the 10 ideas per target are fixed in the input artifact.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


def get_chat_completion():
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "openai_compatible_client",
        PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.chat_completion


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
            return None
    return None


def judge_idea(chat_completion, idea: dict, target_title: str, target_contribution: str,
               model: str, sleep_seconds: float) -> dict:
    prompt = JUDGE_PROMPT.format(
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
        provider="sjtu",
        temperature=0.0,
        max_tokens=512,
        sleep_seconds=sleep_seconds,
    )
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
        match_val = parsed.get("match")
        if isinstance(match_val, bool):
            judgment["match"] = match_val
            judgment["confidence"] = float(parsed.get("confidence", 0.0) or 0.0)
            judgment["reason"] = str(parsed.get("reason", ""))[:1000]
            judgment["parse_status"] = "ok"
        elif isinstance(match_val, str):
            judgment["parse_status"] = "string_boolean"
            judgment["reason"] = str(parsed.get("reason", ""))[:1000]
        else:
            judgment["parse_status"] = "invalid_match_type"
            judgment["reason"] = str(parsed.get("reason", ""))[:1000]
    elif not raw:
        judgment["parse_status"] = "empty_response"
    return judgment


def load_jsonl_by_id(path: Path) -> dict:
    records = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                records[rec["target_id"]] = rec
    return records


def validate_generation_artifact(generation: dict) -> list[str]:
    issues = []
    if generation.get("any_leakage_detected") is not False:
        issues.append("any_leakage_detected_not_false")
    if generation.get("completed") != 77:
        issues.append(f"completed_not_77:{generation.get('completed')}")
    if generation.get("total_ideas") != 770:
        issues.append(f"total_ideas_not_770:{generation.get('total_ideas')}")
    if generation.get("generation_parse_rate") != 100:
        issues.append(f"generation_parse_rate_not_100:{generation.get('generation_parse_rate')}")

    seen = set()
    for target in generation.get("targets", []):
        target_id = target.get("target_id")
        if target_id in seen:
            issues.append(f"duplicate_target:{target_id}")
        seen.add(target_id)
        if "target_title" in target or "target_contribution" in target:
            issues.append(f"target_visible_field_in_generation:{target_id}")
        if target.get("generation", {}).get("parse_status") != "ok":
            issues.append(f"generation_parse_not_ok:{target_id}")
        if len(target.get("generated_ideas", [])) != 10:
            issues.append(f"idea_count_not_10:{target_id}:{len(target.get('generated_ideas', []))}")
        if target.get("leakage_issues"):
            issues.append(f"leakage_issues:{target_id}")
    if len(seen) != 77:
        issues.append(f"unique_target_count_not_77:{len(seen)}")
    return issues


def main():
    parser = argparse.ArgumentParser(description="Evaluate clean Direct-10 generations with ZhiYuan judge")
    parser.add_argument(
        "--generation",
        default=str(PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1" / "generation_direct10_glm-51_targethidden-cleanctx_77t_20260614.json"),
    )
    parser.add_argument(
        "--eval-data",
        default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"),
    )
    parser.add_argument("--model", default=os.environ.get("SJTU_MODEL_ID", "glm-5.1"))
    parser.add_argument("--output")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model_slug = safe_model_slug(args.model)
    generation_path = Path(args.generation)
    output_path = Path(args.output) if args.output else (
        PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1" /
        f"evaluation_direct10_glm-51_{model_slug}_selfjudge_cleanctx_77t_20260614.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generation = json.loads(generation_path.read_text())
    eval_data = load_jsonl_by_id(Path(args.eval_data))
    issues = validate_generation_artifact(generation)
    if issues:
        print("GENERATION ARTIFACT INVALID:")
        for issue in issues[:50]:
            print(f"  - {issue}")
        return 1

    targets = generation.get("targets", [])
    if args.limit:
        targets = targets[:args.limit]

    print(f"Loaded generation targets: {len(targets)}")
    print(f"Generation artifact: {generation_path.name}")
    print(f"Judge model: {args.model}")
    print(f"Output: {output_path}")

    if args.dry_run:
        missing_eval = [t["target_id"] for t in targets if t["target_id"] not in eval_data]
        print(f"Missing eval records: {len(missing_eval)}")
        for target in targets[:3]:
            print(f"  {target['target_id']}: {len(target.get('generated_ideas', []))} fixed ideas")
        return 0 if not missing_eval else 1

    completed_ids = set()
    results = []
    total_hits = 0
    judge_parse_ok = 0
    judge_parse_fail = 0
    total_input_tokens = 0
    total_output_tokens = 0
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text())
        kept_results = []
        seen_existing = set()
        dropped_records = 0
        for r in existing.get("targets", []):
            target_id = r.get("target_id")
            judgments = r.get("judgments", [])
            if not target_id or target_id in seen_existing or len(judgments) != 10:
                dropped_records += 1
                continue
            kept_results.append(r)
            seen_existing.add(target_id)

        results = kept_results
        completed_ids = {r["target_id"] for r in results}
        total_hits = sum(1 for r in results if r.get("hit") is True)
        for r in results:
            for j in r.get("judgments", []):
                total_input_tokens += j.get("input_tokens") or 0
                total_output_tokens += j.get("output_tokens") or 0
                if j.get("parse_status") == "ok":
                    judge_parse_ok += 1
                else:
                    judge_parse_fail += 1
        print(f"Resuming: {len(completed_ids)} completed targets")
        if dropped_records:
            print(f"Dropped {dropped_records} incomplete/duplicate existing target records before resume")

    remaining = [t for t in targets if t["target_id"] not in completed_ids]
    chat_completion = get_chat_completion()

    def write_checkpoint():
        completed = len(results)
        total_judgments = judge_parse_ok + judge_parse_fail
        output = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "kind": "evaluation_direct10_cleanctx_zhiyuan_selfjudge",
            "generator_model": generation.get("generator_model"),
            "judge_model": args.model,
            "generation_file": generation_path.name,
            "eval_data": Path(args.eval_data).name,
            "prompt_version": "same_core_research_direction_enriched_v1",
            "context_mode": generation.get("context_mode"),
            "total_targets": len(targets),
            "completed": completed,
            "expected_judgments": len(targets) * 10,
            "total_judgments": total_judgments,
            "all_complete": completed == len(targets) and total_judgments == len(targets) * 10,
            "hits": total_hits,
            "hit_at_10": round(total_hits / max(completed, 1) * 100, 1),
            "judge_parse_ok": judge_parse_ok,
            "judge_parse_fail": judge_parse_fail,
            "judge_parse_rate": round(judge_parse_ok / max(total_judgments, 1) * 100, 1),
            "generation_total_input_tokens": generation.get("total_input_tokens"),
            "generation_total_output_tokens": generation.get("total_output_tokens"),
            "judge_total_input_tokens": total_input_tokens,
            "judge_total_output_tokens": total_output_tokens,
            "judge_total_tokens": total_input_tokens + total_output_tokens,
            "targets": results,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    for idx, target in enumerate(remaining, 1):
        target_id = target["target_id"]
        eval_rec = eval_data.get(target_id)
        if not eval_rec:
            raise RuntimeError(f"Missing eval record for {target_id}")
        target_title = eval_rec.get("title", "")
        target_contribution = eval_rec.get("contribution", "")
        if not target_contribution:
            raise RuntimeError(f"Missing enriched contribution for {target_id}")

        print(f"\n[{idx}/{len(remaining)}] {target_id}: {target_title[:70]}...")
        judgments = []
        hit = False
        for idea_idx, idea in enumerate(target.get("generated_ideas", [])):
            try:
                judgment = judge_idea(
                    chat_completion,
                    idea,
                    target_title,
                    target_contribution,
                    args.model,
                    args.sleep_seconds,
                )
            except Exception as exc:
                err = str(exc).lower()
                if "429" in err or "rate" in err or "limit" in err:
                    print(f"  Rate/API limit at idea {idea_idx}; sleeping 30s then retrying once")
                    time.sleep(30)
                    judgment = judge_idea(
                        chat_completion,
                        idea,
                        target_title,
                        target_contribution,
                        args.model,
                        args.sleep_seconds,
                    )
                else:
                    judgment = {
                        "match": False,
                        "confidence": 0.0,
                        "reason": str(exc)[:300],
                        "raw_response": "",
                        "parse_status": "api_error",
                        "input_tokens": None,
                        "output_tokens": None,
                    }
            judgment["idea_index"] = idea_idx
            judgments.append(judgment)
            total_input_tokens += judgment.get("input_tokens") or 0
            total_output_tokens += judgment.get("output_tokens") or 0
            if judgment.get("parse_status") == "ok":
                judge_parse_ok += 1
            else:
                judge_parse_fail += 1
            if judgment.get("match") is True:
                hit = True
                print(f"  Idea {idea_idx + 1}: MATCH")
        if hit:
            total_hits += 1
            print(f"  HIT ({total_hits}/{len(results) + 1})")
        else:
            print("  MISS")

        results.append({
            "target_id": target_id,
            "target_title": target_title,
            "target_contribution": target_contribution,
            "generated_ideas": target.get("generated_ideas", []),
            "judgments": judgments,
            "hit": hit,
            "timestamp": datetime.now().isoformat(),
        })
        write_checkpoint()
        print(f"  Checkpoint saved: {output_path}")

    write_checkpoint()
    print("\nEvaluation complete")
    print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
