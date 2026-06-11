#!/usr/bin/env python3
"""
Run vanilla MiMo Hit@10 baseline on the Sci-Reasoning eval set.

For each target paper:
1. Give MiMo only predecessor information (no target title/contribution).
2. Ask for exactly 10 research ideas.
3. Parse ideas into structured JSON.
4. Judge each idea against the target title and contribution.
5. Hit@10 is true if any idea matches.

Supports --resume, checkpoints after every paper, retries on rate limits.
"""

import json
import os
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

# ──────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────

GENERATION_PROMPT = """You are an expert AI researcher. Given the following set of predecessor papers that influenced a research direction, generate exactly 10 distinct research ideas that could advance this direction.

## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis_narrative}

## Task

Generate exactly 10 research ideas that could be the next step in this research direction. Each idea should:

1. Build directly on the predecessors listed above.
2. Be specific enough that another researcher could evaluate whether it is worth pursuing.
3. Address a clear gap, limitation, or opportunity identified in the predecessors.

## Output Format

Return a JSON array of exactly 10 objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses

Return ONLY the JSON array, no other text."""

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


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def format_predecessors(predecessors: list[dict]) -> str:
    lines = []
    for i, pw in enumerate(predecessors, 1):
        title = pw.get("title", "Unknown")
        role = pw.get("role", "")
        rel = pw.get("relationship_sentence", "")
        lines.append(f"{i}. **{title}**")
        if role:
            lines.append(f"   - Role: {role}")
        if rel:
            lines.append(f"   - Relationship: {rel}")
    return "\n".join(lines)


def parse_json_from_response(text: str) -> list | dict | None:
    """Extract JSON from model response, handling markdown code blocks."""
    # Try direct parse
    text = text.strip()
    if text.startswith("```"):
        # Remove code block markers
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array or object
    for pattern in [r"\[[\s\S]*\]", r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None


def generate_ideas(record: dict, model: str, sleep_seconds: float) -> dict:
    """Generate 10 ideas for a target paper using vanilla MiMo."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = GENERATION_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.7, max_tokens=4096,
        sleep_seconds=sleep_seconds,
    )

    raw_content = result["content"]
    parsed = parse_json_from_response(raw_content)

    ideas = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                ideas.append({
                    "idea_title": item.get("idea_title", ""),
                    "idea_description": item.get("idea_description", ""),
                    "key_innovation": item.get("key_innovation", ""),
                    "addressed_gap": item.get("addressed_gap", ""),
                })

    return {
        "raw_output": raw_content,
        "parsed_ideas": ideas,
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }


def judge_idea(
    idea: dict, target_title: str, target_contribution: str,
    model: str, sleep_seconds: float,
) -> dict:
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
        messages, model=model, temperature=0.0, max_tokens=512,
        sleep_seconds=sleep_seconds,
    )

    raw = result["content"]
    parsed = parse_json_from_response(raw)

    judgment = {
        "match": False,
        "confidence": 0.0,
        "reason": raw[:300],
    }
    if isinstance(parsed, dict):
        judgment["match"] = bool(parsed.get("match", False))
        judgment["confidence"] = float(parsed.get("confidence", 0.0))
        judgment["reason"] = parsed.get("reason", "")

    judgment["input_tokens"] = result.get("input_tokens")
    judgment["output_tokens"] = result.get("output_tokens")
    return judgment


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Run vanilla MiMo Hit@10 baseline")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "baseline_mimo.json"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load eval data
    records = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    if args.limit:
        records = records[:args.limit]
    print(f"Loaded {len(records)} target papers")

    # Load existing results for resume
    completed_ids = set()
    results = []
    if args.resume and output_path.exists():
        with open(output_path) as f:
            existing = json.load(f)
        results = existing.get("targets", [])
        completed_ids = {r["target_id"] for r in results}
        print(f"Resuming: {len(completed_ids)} already completed")

    # Filter to remaining
    remaining = [r for r in records if r["target_id"] not in completed_ids]
    print(f"Processing {len(remaining)} remaining targets")

    # Stats - recompute from loaded results when resuming
    total_input_tokens = 0
    total_output_tokens = 0
    total_hits = 0
    failures = []
    if args.resume and results:
        for r in results:
            if r.get("hit"):
                total_hits += 1
            gen = r.get("generation", {})
            total_input_tokens += gen.get("input_tokens") or 0
            total_output_tokens += gen.get("output_tokens") or 0
            for j in r.get("judgments", []):
                total_input_tokens += j.get("input_tokens") or 0
                total_output_tokens += j.get("output_tokens") or 0
        print(f"Resume stats: {total_hits} hits, {total_input_tokens} in-tokens, {total_output_tokens} out-tokens")

    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        target_title = record.get("title", "")
        target_contribution = record.get("contribution", target_title)  # fallback to title
        print(f"\n[{idx+1}/{len(remaining)}] {target_title[:60]}...")

        try:
            # Generate ideas
            gen_result = generate_ideas(record, args.model, args.sleep_seconds)
            ideas = gen_result["parsed_ideas"]
            total_input_tokens += gen_result.get("input_tokens") or 0
            total_output_tokens += gen_result.get("output_tokens") or 0
            print(f"  Generated {len(ideas)} ideas ({gen_result.get('elapsed_seconds', 0):.1f}s)")

            # Judge each idea
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
                    judgments.append({
                        "idea_index": idea_idx,
                        "match": False,
                        "confidence": 0.0,
                        "reason": f"Judge error: {str(e)[:200]}",
                    })
                    print(f"  Judge error on idea {idea_idx}: {e}")

            if hit:
                total_hits += 1
                print(f"  HIT! ({total_hits}/{len(results) + idx + 1})")
            else:
                print(f"  MISS")

            # Log token usage
            log_target_completion(
                run_name="baseline_mimo",
                target_id=target_id,
                stage="evaluation",
                num_api_calls=1 + len(judgments),  # generation + judgments
                input_tokens=gen_result.get("input_tokens") or 0,
                output_tokens=gen_result.get("output_tokens") or 0,
                hit=hit,
                num_candidates=len(ideas),
            )

            # Save result
            target_result = {
                "target_id": target_id,
                "target_title": target_title,
                "target_contribution": target_contribution,
                "num_predecessors": len(record.get("predecessors", [])),
                "generated_ideas": ideas,
                "judgments": judgments,
                "hit": hit,
                "generation": {
                    "raw_output": gen_result["raw_output"][:2000],
                    "input_tokens": gen_result.get("input_tokens"),
                    "output_tokens": gen_result.get("output_tokens"),
                    "elapsed_seconds": gen_result.get("elapsed_seconds"),
                },
                "timestamp": datetime.now().isoformat(),
            }
            results.append(target_result)

            # Checkpoint
            checkpoint = {
                "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "model": args.model,
                "sleep_seconds": args.sleep_seconds,
                "total_targets": len(records),
                "completed": len(results),
                "hits": total_hits,
                "hit_at_10": round(total_hits / max(len(results), 1) * 100, 1),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "targets": results,
            }
            with open(output_path, "w") as f:
                json.dump(checkpoint, f, indent=2, ensure_ascii=False)

        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str or "limit" in err_str:
                print(f"  Rate limited, waiting 30s and retrying...")
                time.sleep(30)
                # Retry once
                try:
                    gen_result = generate_ideas(record, args.model, args.sleep_seconds)
                    ideas = gen_result["parsed_ideas"]
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
                            if judgment.get("match"):
                                hit = True
                        except Exception:
                            judgments.append({"idea_index": idea_idx, "match": False, "confidence": 0.0, "reason": "judge error"})
                    if hit:
                        total_hits += 1
                    results.append({
                        "target_id": target_id,
                        "target_title": target_title,
                        "target_contribution": target_contribution,
                        "generated_ideas": ideas,
                        "judgments": judgments,
                        "hit": hit,
                        "timestamp": datetime.now().isoformat(),
                    })
                    # Checkpoint
                    with open(output_path, "w") as f:
                        json.dump({
                            "model": args.model, "total_targets": len(records),
                            "completed": len(results), "hits": total_hits,
                            "hit_at_10": round(total_hits / max(len(results), 1) * 100, 1),
                            "targets": results,
                        }, f, indent=2, ensure_ascii=False)
                except Exception as e2:
                    failures.append({"target_id": target_id, "title": target_title[:80], "error": str(e2)[:300]})
                    print(f"  FAILED after retry: {e2}")
            else:
                failures.append({"target_id": target_id, "title": target_title[:80], "error": str(e)[:300]})
                print(f"  FAILED: {e}")

    # Final summary
    completed = len(results)
    hit_rate = round(total_hits / max(completed, 1) * 100, 1)
    print(f"\n{'='*50}")
    print(f"Baseline Results:")
    print(f"  Completed: {completed}/{len(records)}")
    print(f"  Hits: {total_hits}")
    print(f"  Hit@10: {hit_rate}%")
    print(f"  Failed: {len(failures)}")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens}")

    # Write final
    final = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "model": args.model,
        "sleep_seconds": args.sleep_seconds,
        "total_targets": len(records),
        "completed": completed,
        "hits": total_hits,
        "hit_at_10": hit_rate,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "failures": failures,
        "targets": results,
    }
    with open(output_path, "w") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
