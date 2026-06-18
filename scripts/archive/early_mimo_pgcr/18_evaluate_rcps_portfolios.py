#!/usr/bin/env python3
"""
Evaluate RCPS portfolios using strict JSON judge.

Judges final selected ideas against target title and enriched contribution.
Stores raw responses, parsed JSON, parse status, finish reason, and token usage.

Output: JSON files with evaluation results.
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

# Strict short judge prompt
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

Return ONLY a compact JSON object (no markdown fences, no extra text):
{{"match": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}

Keep the reason under 20 words. Do not add any text before or after the JSON object."""


def judge_idea(idea: dict, target_title: str, target_contribution: str,
               model: str, sleep_seconds: float) -> dict:
    """Judge whether one idea matches the target paper."""
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
        messages, model=model, temperature=0.0, max_tokens=2048,
        sleep_seconds=sleep_seconds,
    )

    raw = result["content"]
    # Strip markdown fences if present
    raw_clean = raw.strip()
    if raw_clean.startswith("```"):
        raw_clean = re.sub(r"^```(?:json)?\s*\n?", "", raw_clean)
        raw_clean = re.sub(r"\n?```\s*$", "", raw_clean)
        raw_clean = raw_clean.strip()

    judgment = {
        "match": False,
        "confidence": 0.0,
        "reason": "",
        "raw_response": raw,
        "parse_status": "unknown",
    }

    if not raw_clean:
        judgment["parse_status"] = "empty_response"
    else:
        try:
            parsed = json.loads(raw_clean)
            if isinstance(parsed, dict):
                judgment["match"] = bool(parsed.get("match", False))
                judgment["confidence"] = float(parsed.get("confidence", 0.0))
                judgment["reason"] = str(parsed.get("reason", ""))[:200]
                judgment["parse_status"] = "ok"
            else:
                judgment["parse_status"] = "not_dict"
        except json.JSONDecodeError:
            judgment["parse_status"] = "json_error"

    judgment["input_tokens"] = result.get("input_tokens")
    judgment["output_tokens"] = result.get("output_tokens")
    judgment["finish_reason"] = result.get("finish_reason")
    judgment["elapsed_seconds"] = result.get("elapsed_seconds")
    return judgment


def main():
    parser = argparse.ArgumentParser(description="Evaluate RCPS portfolios")
    parser.add_argument("--method", required=True, help="Method name (rcps82, rcps55, random_portfolio, diversity_portfolio)")
    parser.add_argument("--input", required=True, help="Selected portfolio JSONL")
    parser.add_argument("--output", required=True, help="Evaluation output JSON")
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument(
        "--allow-legacy-lenient",
        action="store_true",
        help="Required because this script uses the legacy permissive same-direction judge. "
             "Use scripts/19_strict_judge_eval.py for current ACML strict validation.",
    )
    args = parser.parse_args()

    if not args.allow_legacy_lenient:
        raise SystemExit(
            "Refusing to run legacy lenient RCPS evaluator. "
            "Use scripts/19_strict_judge_eval.py for the current strict validation gate, "
            "or pass --allow-legacy-lenient only for explicitly labeled exploratory analysis."
        )

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

    # Load selected portfolio
    records = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} targets with selected ideas")

    # Resume
    completed_ids = set()
    results = []
    total_hits = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_parse_ok = 0
    total_parse_fail = 0

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
                if j.get("parse_status") == "ok":
                    total_parse_ok += 1
                else:
                    total_parse_fail += 1
        completed_ids = {r["target_id"] for r in results}
        print(f"Resuming: {len(completed_ids)} already completed, {total_hits} hits")

    remaining = [r for r in records if r["target_id"] not in completed_ids]
    if args.limit:
        remaining = remaining[:args.limit]
    print(f"Evaluating {len(remaining)} remaining targets")

    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        eval_rec = eval_data.get(target_id, {})
        target_title = eval_rec.get("title", record.get("target_title", ""))
        target_contribution = eval_rec.get("contribution", "")
        if not target_contribution:
            target_contribution = target_title
            print(f"  WARNING: no enriched contribution for {target_id}")

        selected = record.get("selected", [])
        print(f"\n[{idx+1}/{len(remaining)}] {target_title[:60]}... ({len(selected)} ideas)")

        judgments = []
        hit = False
        for idea_idx, idea in enumerate(selected):
            try:
                judgment = judge_idea(
                    idea, target_title, target_contribution,
                    args.model, args.sleep_seconds,
                )
                judgment["idea_index"] = idea_idx
                judgment["slot_source"] = idea.get("slot_source", "unknown")
                judgments.append(judgment)
                total_input_tokens += judgment.get("input_tokens") or 0
                total_output_tokens += judgment.get("output_tokens") or 0
                if judgment.get("parse_status") == "ok":
                    total_parse_ok += 1
                else:
                    total_parse_fail += 1
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
                        judgment["slot_source"] = idea.get("slot_source", "unknown")
                        judgments.append(judgment)
                        if judgment.get("match"):
                            hit = True
                    except Exception:
                        judgments.append({
                            "idea_index": idea_idx,
                            "slot_source": idea.get("slot_source", "unknown"),
                            "match": False,
                            "confidence": 0.0,
                            "reason": "judge error",
                            "parse_status": "error",
                        })
                else:
                    judgments.append({
                        "idea_index": idea_idx,
                        "slot_source": idea.get("slot_source", "unknown"),
                        "match": False,
                        "confidence": 0.0,
                        "reason": str(e)[:200],
                        "parse_status": "error",
                    })

        if hit:
            total_hits += 1
            print(f"  HIT! ({total_hits}/{len(results) + idx + 1})")
        else:
            print(f"  MISS")

        target_result = {
            "target_id": target_id,
            "target_title": target_title,
            "target_contribution": target_contribution,
            "num_selected": len(selected),
            "direct_slots": sum(1 for s in selected if s.get("slot_source") == "direct"),
            "expansion_slots": sum(1 for s in selected if s.get("slot_source", "").startswith("expansion")),
            "selected_ideas": selected,
            "judgments": judgments,
            "hit": hit,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(target_result)

        # Checkpoint
        completed = len(results)
        total_judgments = total_parse_ok + total_parse_fail
        checkpoint = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "method": args.method,
            "model": args.model,
            "eval_data": str(Path(args.eval_data).name),
            "input_data": str(Path(args.input).name),
            "total_targets": len(records),
            "completed": completed,
            "hits": total_hits,
            "hit_at_10": round(total_hits / max(completed, 1) * 100, 1),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "parse_ok": total_parse_ok,
            "parse_fail": total_parse_fail,
            "parse_rate": round(total_parse_ok / max(total_judgments, 1) * 100, 1),
            "targets": results,
        }
        with open(output_path, "w") as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    # Final summary
    completed = len(results)
    hit_rate = round(total_hits / max(completed, 1) * 100, 1)
    total_judgments = total_parse_ok + total_parse_fail
    parse_rate = round(total_parse_ok / max(total_judgments, 1) * 100, 1)

    print(f"\n{'='*50}")
    print(f"{args.method} Evaluation Results:")
    print(f"  Completed: {completed}/{len(records)}")
    print(f"  Hits: {total_hits}")
    print(f"  Hit@10: {hit_rate}%")
    print(f"  Parse rate: {parse_rate}%")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens:,}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    sys.exit(main())
