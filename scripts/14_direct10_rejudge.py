#!/usr/bin/env python3
"""
Rejudge Direct-10 baseline ideas using enriched contributions.

Reads existing baseline_mimo.json ideas and rejudges them with the enriched
eval data that has proper contribution fields (not just title fallback).

Creates: results/acml_direct10_rejudge_mimo_v25pro.json
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
    parser = argparse.ArgumentParser(description="Rejudge Direct-10 with enriched contributions")
    parser.add_argument("--baseline", default=str(PROJECT_ROOT / "results" / "baseline_mimo.json"))
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "acml_direct10_rejudge_mimo_v25pro.json"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load enriched eval data
    eval_data = {}
    with open(args.eval_data) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_data[rec["target_id"]] = rec
    print(f"Loaded {len(eval_data)} enriched eval records")

    # Load baseline results
    with open(args.baseline) as f:
        baseline = json.load(f)
    baseline_targets = baseline["targets"]
    print(f"Loaded {len(baseline_targets)} baseline targets")

    # Resume
    completed_ids = set()
    results = []
    total_hits = 0
    total_input_tokens = 0
    total_output_tokens = 0
    if args.resume and output_path.exists():
        with open(output_path) as f:
            existing = json.load(f)
        results = existing.get("targets", [])
        for r in results:
            if r.get("hit"):
                total_hits += 1
            for j in r.get("judgments", []):
                total_input_tokens += j.get("input_tokens") or 0
                total_output_tokens += j.get("output_tokens") or 0
        completed_ids = {r["target_id"] for r in results}
        print(f"Resuming: {len(completed_ids)} already completed, {total_hits} hits")

    remaining = [t for t in baseline_targets if t["target_id"] not in completed_ids]
    if args.limit:
        remaining = remaining[:args.limit]
    print(f"Rejudging {len(remaining)} remaining targets")

    for idx, target in enumerate(remaining):
        target_id = target["target_id"]
        eval_rec = eval_data.get(target_id, {})
        target_title = eval_rec.get("title", target.get("target_title", ""))
        target_contribution = eval_rec.get("contribution", "")
        if not target_contribution:
            target_contribution = target_title  # fallback
            print(f"  WARNING: no enriched contribution for {target_id}, using title")

        ideas = target.get("generated_ideas", [])
        print(f"\n[{idx+1}/{len(remaining)}] {target_title[:60]}... ({len(ideas)} ideas)")

        judgments = []
        hit = False
        for idea_idx, idea in enumerate(ideas):
            try:
                judgment = judge_idea(
                    idea, target_title, target_contribution,
                    args.model, args.sleep_seconds,
                )
                judgment["idea_index"] = idea_idx
                judgments.append(judgment)
                total_input_tokens += judgment.get("input_tokens") or 0
                total_output_tokens += judgment.get("output_tokens") or 0
                if judgment.get("match"):
                    hit = True
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    print(f"  Rate limited at idea {idea_idx}, waiting 30s...")
                    time.sleep(30)
                    try:
                        judgment = judge_idea(
                            idea, target_title, target_contribution,
                            args.model, args.sleep_seconds,
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

        target_result = {
            "target_id": target_id,
            "target_title": target_title,
            "target_contribution": target_contribution,
            "contribution_source": eval_rec.get("contribution_source", ""),
            "num_predecessors": target.get("num_predecessors", len(eval_rec.get("predecessors", []))),
            "generated_ideas": ideas,
            "judgments": judgments,
            "hit": hit,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(target_result)

        # Checkpoint
        completed = len(results)
        checkpoint = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "method": "direct10_rejudge",
            "model": args.model,
            "eval_data": str(Path(args.eval_data).name),
            "baseline_data": str(Path(args.baseline).name),
            "total_targets": len(baseline_targets),
            "completed": completed,
            "hits": total_hits,
            "hit_at_10": round(total_hits / max(completed, 1) * 100, 1),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "targets": results,
        }
        with open(output_path, "w") as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    # Final summary
    completed = len(results)
    hit_rate = round(total_hits / max(completed, 1) * 100, 1)
    print(f"\n{'='*50}")
    print(f"Direct-10 Rejudge Results (enriched):")
    print(f"  Completed: {completed}/{len(baseline_targets)}")
    print(f"  Hits: {total_hits}")
    print(f"  Hit@10: {hit_rate}%")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens:,}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    sys.exit(main())
