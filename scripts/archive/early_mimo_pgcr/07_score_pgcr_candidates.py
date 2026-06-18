#!/usr/bin/env python3
"""
PGCR Phase 2: Score candidates using pattern-aware reranker.

Scores each candidate on 6 dimensions (1-5 scale):
- grounding: clearly builds on predecessors
- pattern_fit: matches assigned pattern
- specificity: concrete technical contribution
- plausibility: could plausibly be a top AI paper
- novelty: not merely restating predecessors
- clarity: concise and understandable

Does NOT reveal target title or contribution to the reranker.
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

SCORE_PROMPT = """You are an expert AI research evaluator. Score the following research idea on 6 dimensions.

## Context: Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis_narrative}

## Innovation Pattern: {pattern_name}

## Research Idea to Score

**Title:** {idea_title}
**Description:** {idea_description}
**Key Innovation:** {key_innovation}
**Addressed Gap:** {addressed_gap}
**Pattern Application:** {pattern_application}

## Scoring Dimensions

Rate each dimension from 1 to 5 (1=very poor, 5=excellent):

1. **grounding**: Does this idea clearly build on the predecessor papers? (5=directly extends multiple predecessors, 1=no connection)
2. **pattern_fit**: Does this idea match the "{pattern_name}" innovation pattern? (5=perfect pattern application, 1=does not fit pattern)
3. **specificity**: Is the idea concrete enough to be implemented? (5=specific technical approach, 1=vague hand-waving)
4. **plausibility**: Could this plausibly be a top AI paper? (5=strong publication potential, 1=unrealistic)
5. **novelty**: Is this genuinely new, not just restating predecessors? (5=clearly novel contribution, 1=direct restatement)
6. **clarity**: Is the idea clearly and concisely described? (5=crystal clear, 1=confusing)

## Output Format

Return a JSON object with:
- "grounding": integer 1-5
- "pattern_fit": integer 1-5
- "specificity": integer 1-5
- "plausibility": integer 1-5
- "novelty": integer 1-5
- "clarity": integer 1-5
- "overall": float (weighted average: 0.3*grounding + 0.2*pattern_fit + 0.2*specificity + 0.15*plausibility + 0.1*novelty + 0.05*clarity)
- "brief_reason": one sentence explaining the overall score

Return ONLY the JSON object, no other text."""


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
    for pattern in [r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None


def score_candidate(candidate: dict, record_context: dict, model: str, sleep_seconds: float) -> dict:
    """Score a single candidate."""
    predecessors_text = format_predecessors(record_context.get("predecessors", []))
    synthesis = record_context.get("synthesis_narrative", "")

    prompt = SCORE_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
        pattern_name=candidate.get("pattern", ""),
        idea_title=candidate.get("idea_title", ""),
        idea_description=candidate.get("idea_description", ""),
        key_innovation=candidate.get("key_innovation", ""),
        addressed_gap=candidate.get("addressed_gap", ""),
        pattern_application=candidate.get("pattern_application", ""),
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.0, max_tokens=512,
        sleep_seconds=sleep_seconds,
    )

    parsed = parse_json_from_response(result["content"])
    scores = {
        "grounding": 3,
        "pattern_fit": 3,
        "specificity": 3,
        "plausibility": 3,
        "novelty": 3,
        "clarity": 3,
        "overall": 3.0,
        "brief_reason": "",
    }
    if isinstance(parsed, dict):
        for dim in ["grounding", "pattern_fit", "specificity", "plausibility", "novelty", "clarity"]:
            if dim in parsed:
                scores[dim] = max(1, min(5, int(parsed[dim])))
        # Recompute overall
        scores["overall"] = round(
            0.3 * scores["grounding"] + 0.2 * scores["pattern_fit"] +
            0.2 * scores["specificity"] + 0.15 * scores["plausibility"] +
            0.1 * scores["novelty"] + 0.05 * scores["clarity"], 2
        )
        scores["brief_reason"] = parsed.get("brief_reason", "")

    scores["input_tokens"] = result.get("input_tokens")
    scores["output_tokens"] = result.get("output_tokens")
    return scores


def main():
    parser = argparse.ArgumentParser(description="PGCR candidate scoring")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "results" / "pgcr_candidates.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "pgcr_scored.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load candidates
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
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    results.append(obj)
                    completed_ids.add(obj.get("target_id", ""))
        print(f"Resuming: {len(completed_ids)} already completed")

    remaining = [r for r in records if r["target_id"] not in completed_ids]
    print(f"Processing {len(remaining)} remaining targets")

    # Load eval data for predecessor context
    eval_path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"
    eval_context = {}
    with open(eval_path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_context[rec["target_id"]] = rec

    total_tokens = 0
    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        candidates = record.get("candidates", [])
        print(f"\n[{idx+1}/{len(remaining)}] {record.get('target_title', '')[:50]}... ({len(candidates)} candidates)")

        context = eval_context.get(target_id, {})
        scored_candidates = []

        for c_idx, cand in enumerate(candidates):
            try:
                scores = score_candidate(cand, context, args.model, args.sleep_seconds)
                cand["scores"] = scores
                total_tokens += (scores.get("input_tokens") or 0) + (scores.get("output_tokens") or 0)
                scored_candidates.append(cand)
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    print(f"  Rate limited at candidate {c_idx}, waiting 30s...")
                    time.sleep(30)
                    try:
                        scores = score_candidate(cand, context, args.model, args.sleep_seconds)
                        cand["scores"] = scores
                        scored_candidates.append(cand)
                    except Exception:
                        cand["scores"] = {"overall": 0, "brief_reason": "scoring failed"}
                        scored_candidates.append(cand)
                else:
                    cand["scores"] = {"overall": 0, "brief_reason": f"error: {str(e)[:100]}"}
                    scored_candidates.append(cand)

        # Log token usage for this target
        target_in = sum(c.get("scores", {}).get("input_tokens", 0) for c in scored_candidates)
        target_out = sum(c.get("scores", {}).get("output_tokens", 0) for c in scored_candidates)
        log_target_completion(
            run_name="pgcr_scoring",
            target_id=target_id,
            stage="scoring",
            num_api_calls=len(scored_candidates),
            input_tokens=target_in,
            output_tokens=target_out,
            num_candidates=len(scored_candidates),
        )

        result_obj = {
            "target_id": target_id,
            "target_title": record.get("target_title", ""),
            "total_candidates": len(scored_candidates),
            "candidates": scored_candidates,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(result_obj)

        with open(output_path, "a") as f:
            f.write(json.dumps(result_obj, ensure_ascii=False) + "\n")

        avg_score = round(
            sum(c.get("scores", {}).get("overall", 0) for c in scored_candidates) /
            max(len(scored_candidates), 1), 2
        )
        print(f"  Avg overall score: {avg_score}")

    print(f"\n{'='*50}")
    print(f"Scoring complete: {len(results)} targets, {total_tokens:,} tokens")


if __name__ == "__main__":
    sys.exit(main())
