#!/usr/bin/env python3
"""
PGCR Phase 4: Evaluate Top-10 selected ideas using the same judge as baseline.

Uses identical judge prompt and protocol as 03_run_baseline_mimo.py.
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from mimo_client import chat_completion
from experiment_logger import log_target_completion

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


def parse_json_from_response(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None


def judge_idea(idea: dict, target_title: str, target_contribution: str,
               model: str, sleep_seconds: float) -> dict:
    prompt = JUDGE_PROMPT.format(
        target_title=target_title,
        target_contribution=target_contribution,
        idea_title=idea.get("idea_title", ""),
        idea_description=idea.get("idea_description", ""),
        key_innovation=idea.get("key_innovation", ""),
        addressed_gap=idea.get("addressed_gap", ""),
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.0, max_tokens=512,
        sleep_seconds=sleep_seconds,
    )

    parsed = parse_json_from_response(result["content"])
    judgment = {"match": False, "confidence": 0.0, "reason": result["content"][:300]}
    if isinstance(parsed, dict):
        judgment["match"] = bool(parsed.get("match", False))
        judgment["confidence"] = float(parsed.get("confidence", 0.0))
        judgment["reason"] = parsed.get("reason", "")

    judgment["input_tokens"] = result.get("input_tokens")
    judgment["output_tokens"] = result.get("output_tokens")
    return judgment


def main():
    parser = argparse.ArgumentParser(description="Evaluate PGCR Top-10")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "results" / "pgcr_top10.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "pgcr_full.json"))
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"))
    parser.add_argument("--judge-model", default="mimo-v2.5-pro")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load eval data for target titles/contributions
    eval_data = {}
    with open(args.eval_data) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_data[rec["target_id"]] = rec

    # Load PGCR top-10
    records = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} targets")

    # Resume
    completed_ids = set()
    results = []
    if args.resume and output_path.exists():
        with open(output_path) as f:
            existing = json.load(f)
        results = existing.get("targets", [])
        completed_ids = {r["target_id"] for r in results}
        print(f"Resuming: {len(completed_ids)} already completed")

    remaining = [r for r in records if r["target_id"] not in completed_ids]
    print(f"Processing {len(remaining)} remaining targets")

    # Recompute stats from loaded results when resuming
    total_hits = 0
    total_tokens = 0
    if args.resume and results:
        for r in results:
            if r.get("hit"):
                total_hits += 1
            for j in r.get("judgments", []):
                total_tokens += (j.get("input_tokens") or 0) + (j.get("output_tokens") or 0)
        print(f"Resume stats: {total_hits} hits, {total_tokens} total tokens")

    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        eval_rec = eval_data.get(target_id, {})
        target_title = eval_rec.get("title", record.get("target_title", ""))
        target_contribution = eval_rec.get("contribution", target_title)
        selected = record.get("selected", [])

        print(f"\n[{idx+1}/{len(remaining)}] {target_title[:60]}... ({len(selected)} ideas)")

        judgments = []
        hit = False

        for idea_idx, idea in enumerate(selected):
            try:
                judgment = judge_idea(
                    idea, target_title, target_contribution,
                    args.judge_model, args.sleep_seconds,
                )
                judgment["idea_index"] = idea_idx
                judgments.append(judgment)
                total_tokens += (judgment.get("input_tokens") or 0) + (judgment.get("output_tokens") or 0)
                if judgment.get("match"):
                    hit = True
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    print(f"  Rate limited, waiting 30s...")
                    time.sleep(30)
                    try:
                        judgment = judge_idea(
                            idea, target_title, target_contribution,
                            args.judge_model, args.sleep_seconds,
                        )
                        judgment["idea_index"] = idea_idx
                        judgments.append(judgment)
                        if judgment.get("match"):
                            hit = True
                    except Exception:
                        judgments.append({"idea_index": idea_idx, "match": False, "confidence": 0.0, "reason": "judge error"})
                else:
                    judgments.append({"idea_index": idea_idx, "match": False, "confidence": 0.0, "reason": str(e)[:200]})

        if hit:
            total_hits += 1
            print(f"  HIT! ({total_hits}/{len(results) + idx + 1})")
        else:
            print(f"  MISS")

        # Log token usage
        target_in = sum(j.get("input_tokens", 0) for j in judgments if j.get("input_tokens"))
        target_out = sum(j.get("output_tokens", 0) for j in judgments if j.get("output_tokens"))
        log_target_completion(
            run_name="pgcr_evaluation",
            target_id=target_id,
            stage="evaluation",
            num_api_calls=len(judgments),
            input_tokens=target_in,
            output_tokens=target_out,
            hit=hit,
            num_candidates=record.get("total_candidates", 0),
        )

        target_result = {
            "target_id": target_id,
            "target_title": target_title,
            "target_contribution": target_contribution,
            "num_candidates": record.get("total_candidates", 0),
            "num_selected": len(selected),
            "selected_ideas": selected,
            "judgments": judgments,
            "hit": hit,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(target_result)

        # Checkpoint
        completed = len(results)
        checkpoint = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "method": "pgcr_full",
            "judge_model": args.judge_model,
            "total_targets": len(records),
            "completed": completed,
            "hits": total_hits,
            "hit_at_10": round(total_hits / max(completed, 1) * 100, 1),
            "total_tokens": total_tokens,
            "targets": results,
        }
        with open(output_path, "w") as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    # Final
    completed = len(results)
    hit_rate = round(total_hits / max(completed, 1) * 100, 1)
    print(f"\n{'='*50}")
    print(f"PGCR Results:")
    print(f"  Completed: {completed}/{len(records)}")
    print(f"  Hits: {total_hits}")
    print(f"  Hit@10: {hit_rate}%")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    sys.exit(main())
