#!/usr/bin/env python3
"""
Score and select top-10 from vanilla expansion candidates.

Reuses the same scoring prompt as PGCR but without pattern_fit dimension.
Selects top-10 by overall score with diversity dedup.
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from mimo_client import chat_completion
from experiment_logger import log_target_completion

SCORE_PROMPT = """You are an expert AI research evaluator. Score the following research idea on 5 dimensions.

## Context: Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis_narrative}

## Research Idea to Score

**Title:** {idea_title}
**Description:** {idea_description}
**Key Innovation:** {key_innovation}
**Addressed Gap:** {addressed_gap}

## Scoring Dimensions

Rate each dimension from 1 to 5 (1=very poor, 5=excellent):

1. **grounding**: Does this idea clearly build on the predecessor papers? (5=directly extends multiple predecessors, 1=no connection)
2. **specificity**: Is the idea concrete enough to be implemented? (5=specific technical approach, 1=vague hand-waving)
3. **plausibility**: Could this plausibly be a top AI paper? (5=strong publication potential, 1=unrealistic)
4. **novelty**: Is this genuinely new, not just restating predecessors? (5=clearly novel contribution, 1=direct restatement)
5. **clarity**: Is the idea clearly and concisely described? (5=crystal clear, 1=confusing)

## Output Format

Return a JSON object with:
- "grounding": integer 1-5
- "specificity": integer 1-5
- "plausibility": integer 1-5
- "novelty": integer 1-5
- "clarity": integer 1-5
- "overall": float (weighted average: 0.35*grounding + 0.25*specificity + 0.2*plausibility + 0.15*novelty + 0.05*clarity)
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
    for pat in [r"\{[\s\S]*\}"]:
        match = re.search(pat, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None


def score_candidate(idea: dict, context: dict, model: str, sleep_seconds: float) -> dict:
    predecessors_text = format_predecessors(context.get("predecessors", []))
    synthesis = context.get("synthesis_narrative", "")

    prompt = SCORE_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
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
    scores = {"grounding": 3, "specificity": 3, "plausibility": 3, "novelty": 3, "clarity": 3, "overall": 3.0, "brief_reason": ""}
    if isinstance(parsed, dict):
        for dim in ["grounding", "specificity", "plausibility", "novelty", "clarity"]:
            if dim in parsed:
                scores[dim] = max(1, min(5, int(parsed[dim])))
        scores["overall"] = round(
            0.35 * scores["grounding"] + 0.25 * scores["specificity"] +
            0.2 * scores["plausibility"] + 0.15 * scores["novelty"] +
            0.05 * scores["clarity"], 2
        )
        scores["brief_reason"] = parsed.get("brief_reason", "")
    scores["input_tokens"] = result.get("input_tokens")
    scores["output_tokens"] = result.get("output_tokens")
    return scores


def normalize_text(text: str) -> set:
    return set(re.findall(r'\w+', text.lower()))


def jaccard_overlap(s1: set, s2: set) -> float:
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def select_top10(candidates: list[dict], threshold: float = 0.6) -> list[dict]:
    scored = [(c, c.get("scores", {}).get("overall", 0)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = []
    selected_words = []
    for cand, score in scored:
        if len(selected) >= 10:
            break
        words = normalize_text(cand.get("idea_title", "") + " " + cand.get("idea_description", ""))
        if any(jaccard_overlap(words, sw) > threshold for sw in selected_words):
            continue
        selected.append(cand)
        selected_words.append(words)
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Vanilla expansion JSONL")
    parser.add_argument("--output", required=True, help="Output top-10 JSONL")
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load eval context
    eval_context = {}
    with open(args.eval_data) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_context[rec["target_id"]] = rec

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

    total_tokens = 0
    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        candidates = record.get("candidates", [])
        context = eval_context.get(target_id, {})
        print(f"\n[{idx+1}/{len(remaining)}] {record.get('target_title', '')[:50]}... ({len(candidates)} candidates)")

        # Score all candidates
        for c_idx, cand in enumerate(candidates):
            try:
                scores = score_candidate(cand, context, args.model, args.sleep_seconds)
                cand["scores"] = scores
                total_tokens += (scores.get("input_tokens") or 0) + (scores.get("output_tokens") or 0)
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str:
                    time.sleep(30)
                    try:
                        scores = score_candidate(cand, context, args.model, args.sleep_seconds)
                        cand["scores"] = scores
                    except Exception:
                        cand["scores"] = {"overall": 0}
                else:
                    cand["scores"] = {"overall": 0}

        # Select top-10
        selected = select_top10(candidates)
        for i, s in enumerate(selected):
            s["rank"] = i + 1

        # Log
        target_in = sum(c.get("scores", {}).get("input_tokens", 0) or 0 for c in candidates)
        target_out = sum(c.get("scores", {}).get("output_tokens", 0) or 0 for c in candidates)
        log_target_completion(
            run_name="vanilla_scoring",
            target_id=target_id,
            stage="scoring",
            num_api_calls=len(candidates),
            input_tokens=target_in,
            output_tokens=target_out,
            num_candidates=len(selected),
        )

        result_obj = {
            "target_id": target_id,
            "target_title": record.get("target_title", ""),
            "total_candidates": len(candidates),
            "selected_count": len(selected),
            "selected": selected,
        }
        results.append(result_obj)

        with open(output_path, "a") as f:
            f.write(json.dumps(result_obj, ensure_ascii=False) + "\n")

        print(f"  Scored {len(candidates)}, selected {len(selected)}")

    print(f"\nTotal tokens: {total_tokens:,}")


if __name__ == "__main__":
    sys.exit(main())
