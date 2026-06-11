#!/usr/bin/env python3
"""
Vanilla expansion baseline: generate many candidates without pattern conditioning.

Tests whether improvement comes from more candidates OR from pattern guidance.
Repeatedly calls vanilla MiMo to generate 10 ideas each time, accumulates 50-100 total.
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
4. Be DIFFERENT from typical ideas in this area — try to be creative and unexpected.

## Output Format

Return a JSON array of exactly 10 objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses

Return ONLY the JSON array, no other text."""


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
    for pattern in [r"\[[\s\S]*\]", r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None


def generate_batch(record: dict, model: str, sleep_seconds: float) -> tuple[list[dict], dict]:
    """Generate one batch of 10 ideas."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = GENERATION_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.9, max_tokens=4096,
        sleep_seconds=sleep_seconds,
    )

    parsed = parse_json_from_response(result["content"])
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

    stats = {
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }
    return ideas, stats


def main():
    parser = argparse.ArgumentParser(description="Vanilla expansion baseline")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "vanilla_expansion.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--batches", type=int, default=5, help="Number of 10-idea batches (5=50 candidates)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--hard-cases-only", action="store_true", help="Only process targets baseline missed")
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

    # Filter to hard cases if requested
    if args.hard_cases_only:
        baseline_path = PROJECT_ROOT / "results" / "baseline_mimo.json"
        if baseline_path.exists():
            baseline = json.load(open(baseline_path))
            miss_ids = {t["target_id"] for t in baseline["targets"] if not t.get("hit")}
            records = [r for r in records if r["target_id"] in miss_ids]
            print(f"Hard cases only: {len(records)} targets baseline missed")
        else:
            print("WARNING: baseline not found, processing all targets")

    if args.limit:
        records = records[:args.limit]
    print(f"Processing {len(records)} targets, {args.batches} batches each")

    # Resume
    completed_ids = set()
    results = []
    if args.resume and output_path.exists():
        with open(output_path) as f:
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    results.append(obj)
                    completed_ids.add(obj.get("target_id", ""))
        print(f"Resuming: {len(completed_ids)} already completed")

    remaining = [r for r in records if r["target_id"] not in completed_ids]
    print(f"Processing {len(remaining)} remaining targets")

    total_tokens = 0
    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        print(f"\n[{idx+1}/{len(remaining)}] {record.get('title', '')[:50]}...")

        all_ideas = []
        batch_stats = []

        for batch_idx in range(args.batches):
            try:
                ideas, stats = generate_batch(record, args.model, args.sleep_seconds)
                for i, idea in enumerate(ideas):
                    idea["candidate_id"] = f"{target_id}_vanilla_{batch_idx}_{i:02d}"
                    idea["batch"] = batch_idx
                all_ideas.extend(ideas)
                batch_stats.append(stats)
                total_tokens += (stats.get("input_tokens") or 0) + (stats.get("output_tokens") or 0)
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    print(f"  Rate limited at batch {batch_idx}, waiting 30s...")
                    time.sleep(30)
                    try:
                        ideas, stats = generate_batch(record, args.model, args.sleep_seconds)
                        for i, idea in enumerate(ideas):
                            idea["candidate_id"] = f"{target_id}_vanilla_{batch_idx}_{i:02d}"
                            idea["batch"] = batch_idx
                        all_ideas.extend(ideas)
                        batch_stats.append(stats)
                    except Exception as e2:
                        print(f"  Batch {batch_idx} failed: {e2}")
                else:
                    print(f"  Batch {batch_idx} failed: {e}")

        result_obj = {
            "target_id": target_id,
            "target_title": record.get("title", ""),
            "total_candidates": len(all_ideas),
            "num_batches": args.batches,
            "candidates": all_ideas,
            "batch_stats": batch_stats,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(result_obj)

        # Log
        target_in = sum(s.get("input_tokens", 0) or 0 for s in batch_stats)
        target_out = sum(s.get("output_tokens", 0) or 0 for s in batch_stats)
        log_target_completion(
            run_name="vanilla_expansion",
            target_id=target_id,
            stage="generation",
            num_api_calls=len(batch_stats),
            input_tokens=target_in,
            output_tokens=target_out,
            num_candidates=len(all_ideas),
        )

        # Append checkpoint
        with open(output_path, "a") as f:
            f.write(json.dumps(result_obj, ensure_ascii=False) + "\n")

        print(f"  Generated {len(all_ideas)} candidates ({len(batch_stats)} batches)")

    total_cands = sum(r["total_candidates"] for r in results)
    print(f"\n{'='*50}")
    print(f"Vanilla Expansion Summary:")
    print(f"  Targets: {len(results)}")
    print(f"  Total candidates: {total_cands}")
    print(f"  Avg per target: {round(total_cands / max(len(results), 1), 1)}")
    print(f"  Total tokens: {total_tokens:,}")


if __name__ == "__main__":
    sys.exit(main())
