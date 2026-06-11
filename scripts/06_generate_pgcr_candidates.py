#!/usr/bin/env python3
"""
PGCR Phase 1: Generate candidates under multiple innovation patterns.

For each target paper, generates candidates under 8 pattern/recipe prompts.
Output: results/pgcr_candidates.jsonl (one JSON object per target)
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

# ──────────────────────────────────────────────────────────────────────
# Pattern definitions
# ──────────────────────────────────────────────────────────────────────

PATTERNS = [
    {
        "id": "gap_driven_reframing",
        "name": "Gap-Driven Reframing",
        "instruction": "Look at the predecessor papers and identify a specific limitation, gap, or mismatched assumption. Reframe the problem so that a different set of methods or objectives becomes applicable.",
    },
    {
        "id": "cross_domain_synthesis",
        "name": "Cross-Domain Synthesis",
        "instruction": "Consider how ideas, methods, or formalisms from a different research domain could be imported to solve the problem described by the predecessors.",
    },
    {
        "id": "representation_shift",
        "name": "Representation Shift",
        "instruction": "Identify a core primitive, data structure, or representation used by the predecessors. Propose replacing it with something that simplifies the problem or unlocks new capabilities.",
    },
    {
        "id": "data_evaluation_engineering",
        "name": "Data & Evaluation Engineering",
        "instruction": "Design a new dataset, benchmark, or evaluation protocol that would reveal gaps in the existing approaches described by the predecessors.",
    },
    {
        "id": "formal_experimental_tightening",
        "name": "Formal-Experimental Tightening",
        "instruction": "Identify theoretical claims in the predecessors that could be tightened with formal analysis, or propose experiments that would validate or challenge existing theory.",
    },
    {
        "id": "gap_representation",
        "name": "Gap-Driven Reframing + Representation Shift",
        "instruction": "Combine two strategies: (1) identify a limitation or gap in the predecessors, and (2) propose a new representation or primitive that reframes the problem to address that gap.",
    },
    {
        "id": "cross_domain_representation",
        "name": "Cross-Domain Synthesis + Representation Shift",
        "instruction": "Combine two strategies: (1) import an idea from a different domain, and (2) propose a new representation or data structure that makes that import feasible.",
    },
    {
        "id": "gap_cross_domain",
        "name": "Gap-Driven Reframing + Cross-Domain Synthesis",
        "instruction": "Combine two strategies: (1) identify a gap in the predecessors, and (2) find a solution approach from a different research domain that directly addresses that gap.",
    },
]

PATTERN_PROMPT = """You are an expert AI researcher specializing in the "{pattern_name}" innovation pattern.

## Innovation Pattern: {pattern_name}

{pattern_instruction}

## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis_narrative}

## Task

Using the "{pattern_name}" innovation pattern, generate exactly {candidates_per_pattern} distinct research ideas that could advance the research direction described by the predecessors above.

Each idea must:
1. Clearly apply the "{pattern_name}" pattern.
2. Build directly on the predecessors listed above.
3. Be specific enough that another researcher could evaluate whether it is worth pursuing.
4. Address a clear gap, limitation, or opportunity identified in the predecessors.

## Output Format

Return a JSON array of exactly {candidates_per_pattern} objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses
- "pattern_application": How the "{pattern_name}" pattern specifically informed this idea

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


def generate_for_pattern(record: dict, pattern: dict, model: str,
                         candidates_per_pattern: int, sleep_seconds: float) -> list[dict]:
    """Generate candidates for one pattern."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = PATTERN_PROMPT.format(
        pattern_name=pattern["name"],
        pattern_instruction=pattern["instruction"],
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
        candidates_per_pattern=candidates_per_pattern,
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.8, max_tokens=4096,
        sleep_seconds=sleep_seconds,
    )

    parsed = parse_json_from_response(result["content"])
    candidates = []
    if isinstance(parsed, list):
        for i, item in enumerate(parsed):
            if isinstance(item, dict):
                candidates.append({
                    "candidate_id": f"{record['target_id']}_{pattern['id']}_{i:02d}",
                    "target_id": record["target_id"],
                    "pattern": pattern["name"],
                    "pattern_id": pattern["id"],
                    "idea_title": item.get("idea_title", ""),
                    "idea_description": item.get("idea_description", ""),
                    "key_innovation": item.get("key_innovation", ""),
                    "addressed_gap": item.get("addressed_gap", ""),
                    "pattern_application": item.get("pattern_application", ""),
                })

    return candidates, {
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }


def main():
    parser = argparse.ArgumentParser(description="PGCR candidate generation")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "pgcr_candidates.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--candidates-per-pattern", type=int, default=12)
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
    print(f"Loaded {len(records)} targets, {len(PATTERNS)} patterns")
    print(f"Expected candidates per target: {args.candidates_per_pattern * len(PATTERNS)}")

    # Resume support
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
        target_title = record.get("title", "")[:60]
        print(f"\n[{idx+1}/{len(remaining)}] {target_title}...")

        all_candidates = []
        pattern_stats = {}
        failed_patterns = []

        for p_idx, pattern in enumerate(PATTERNS):
            try:
                candidates, stats = generate_for_pattern(
                    record, pattern, args.model,
                    args.candidates_per_pattern, args.sleep_seconds,
                )
                if len(candidates) == 0:
                    failed_patterns.append(pattern["id"])
                    print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: 0 candidates (parse failure)")
                else:
                    all_candidates.extend(candidates)
                    pattern_stats[pattern["id"]] = {
                        "generated": len(candidates),
                        "input_tokens": stats.get("input_tokens"),
                        "output_tokens": stats.get("output_tokens"),
                    }
                    total_tokens += (stats.get("input_tokens") or 0) + (stats.get("output_tokens") or 0)
                    print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: {len(candidates)} candidates")
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    print(f"  Rate limited on {pattern['name']}, waiting 30s...")
                    time.sleep(30)
                    try:
                        candidates, stats = generate_for_pattern(
                            record, pattern, args.model,
                            args.candidates_per_pattern, args.sleep_seconds,
                        )
                        if len(candidates) == 0:
                            failed_patterns.append(pattern["id"])
                            print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: 0 candidates after retry")
                        else:
                            all_candidates.extend(candidates)
                            pattern_stats[pattern["id"]] = {
                                "generated": len(candidates),
                                "input_tokens": stats.get("input_tokens"),
                                "output_tokens": stats.get("output_tokens"),
                            }
                            print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: {len(candidates)} candidates (retry)")
                    except Exception as e2:
                        failed_patterns.append(pattern["id"])
                        print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: FAILED ({e2})")
                else:
                    failed_patterns.append(pattern["id"])
                    print(f"  [{p_idx+1}/{len(PATTERNS)}] {pattern['name']}: FAILED ({e})")

        result_obj = {
            "target_id": target_id,
            "target_title": record.get("title", ""),
            "num_predecessors": len(record.get("predecessors", [])),
            "primary_pattern": record.get("primary_pattern", ""),
            "total_candidates": len(all_candidates),
            "pattern_stats": pattern_stats,
            "failed_patterns": failed_patterns,
            "candidates": all_candidates,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(result_obj)

        # Append checkpoint
        with open(output_path, "a") as f:
            f.write(json.dumps(result_obj, ensure_ascii=False) + "\n")

        print(f"  Total candidates: {len(all_candidates)}")

    # Summary
    total_cands = sum(r["total_candidates"] for r in results)
    avg_cands = round(total_cands / max(len(results), 1), 1)
    print(f"\n{'='*50}")
    print(f"Candidate Generation Summary:")
    print(f"  Targets: {len(results)}")
    print(f"  Total candidates: {total_cands}")
    print(f"  Avg candidates/target: {avg_cands}")
    print(f"  Total tokens: {total_tokens:,}")


if __name__ == "__main__":
    sys.exit(main())
