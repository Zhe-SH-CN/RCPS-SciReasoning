#!/usr/bin/env python3
"""
Cross-model Direct-10 smoke test.

Runs Direct-10 generation + self-judge on the first 3 targets using a cross-model provider.
Target-hidden: generation does not see target title or contribution.
Judge sees target title and enriched contribution only after ideas are generated.

Output: results/experiments/20260614_cross_model_zhiyuan1/smoke_direct10_<model_slug>_selfjudge_3t_20260614.json
"""

import json
import re
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location("openai_compatible_client", PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
chat_completion = mod.chat_completion
get_sjtu_model = mod.get_sjtu_model
safe_model_slug = mod.safe_model_slug
get_sleep_seconds = mod.get_sleep_seconds

logger = logging.getLogger(__name__)

# Target-hidden generation prompt (no target title or contribution)
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

# Judge prompt (sees target title and contribution)
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
    """Extract JSON from model response, handling markdown code blocks."""
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


def generate_ideas(record: dict, model: str, sleep_seconds: float) -> dict:
    """Generate 10 ideas for a target paper (target-hidden)."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = GENERATION_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, provider="sjtu",
        temperature=0.7, max_tokens=4096,
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
        "parse_status": "ok" if ideas else "parse_failed",
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "finish_reason": result.get("finish_reason"),
    }


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
        messages, model=model, provider="sjtu",
        temperature=0.0, max_tokens=512,
        sleep_seconds=sleep_seconds,
    )

    raw = result["content"]
    parsed = parse_json_from_response(raw)

    judgment = {
        "match": False,
        "confidence": 0.0,
        "reason": "",
        "raw_response": raw,
        "parse_status": "unknown",
    }

    if not raw.strip():
        judgment["parse_status"] = "empty_response"
    elif isinstance(parsed, dict):
        # Strict Boolean check: match must be a real Boolean, not a string
        match_val = parsed.get("match")
        if isinstance(match_val, bool):
            judgment["match"] = match_val
            judgment["confidence"] = float(parsed.get("confidence", 0.0))
            judgment["reason"] = str(parsed.get("reason", ""))[:200]
            judgment["parse_status"] = "ok"
        elif isinstance(match_val, str):
            judgment["parse_status"] = "string_boolean"
        else:
            judgment["parse_status"] = "invalid_match_type"
    else:
        judgment["parse_status"] = "json_error"

    judgment["input_tokens"] = result.get("input_tokens")
    judgment["output_tokens"] = result.get("output_tokens")
    judgment["finish_reason"] = result.get("finish_reason")
    return judgment


def check_target_leakage(prompt: str, target_title: str, target_contribution: str) -> list[str]:
    """Check if prompt contains target title or contribution."""
    issues = []
    if target_title and target_title.lower() in prompt.lower():
        issues.append("target_title_in_prompt")
    if target_contribution and target_contribution.lower() in prompt.lower():
        issues.append("target_contribution_in_prompt")
    return issues


def main():
    parser = argparse.ArgumentParser(description="Cross-model Direct-10 smoke test")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1"))
    parser.add_argument("--model", help="Model ID (overrides SJTU_MODEL_ID env)")
    parser.add_argument("--limit", type=int, default=3, help="Number of targets")
    parser.add_argument("--sleep-seconds", type=float, help="Sleep between calls")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without API calls")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get model ID
    try:
        model_id = args.model or get_sjtu_model()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1

    model_slug = safe_model_slug(model_id)
    sleep_seconds = args.sleep_seconds or get_sleep_seconds()

    print(f"Model: {model_id}")
    print(f"Model slug: {model_slug}")
    print(f"Sleep seconds: {sleep_seconds}")

    # Load eval data
    records = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    records = records[:args.limit]
    print(f"Loaded {len(records)} targets")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for i, rec in enumerate(records):
            print(f"  [{i+1}] {rec['target_id']}: {rec.get('title', '')[:60]}")
            predecessors_text = format_predecessors(rec.get("predecessors", []))
            prompt = GENERATION_PROMPT.format(
                predecessors_text=predecessors_text,
                synthesis_narrative=rec.get("synthesis_narrative", ""),
            )
            # Check for target leakage
            target_title = rec.get("title", "")
            target_contribution = rec.get("contribution", "")
            leakage = check_target_leakage(prompt, target_title, target_contribution)
            if leakage:
                print(f"    WARNING: target leakage: {leakage}")
            else:
                print(f"    No target leakage detected")
        print("\nDry run complete; no API calls made.")
        return 0

    # Run smoke test
    results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_ideas = 0
    parse_ok = 0
    parse_fail = 0
    judge_parse_ok = 0
    judge_parse_fail = 0
    total_hits = 0

    for idx, record in enumerate(records):
        target_id = record["target_id"]
        target_title = record.get("title", "")
        target_contribution = record.get("contribution", "")

        print(f"\n[{idx+1}/{len(records)}] {target_id}: {target_title[:60]}...")

        # Generate ideas (target-hidden)
        try:
            gen_result = generate_ideas(record, model_id, sleep_seconds)
            ideas = gen_result["parsed_ideas"]
            total_input_tokens += gen_result.get("input_tokens") or 0
            total_output_tokens += gen_result.get("output_tokens") or 0
            total_ideas += len(ideas)

            if gen_result["parse_status"] == "ok":
                parse_ok += 1
            else:
                parse_fail += 1

            print(f"  Generated {len(ideas)} ideas (parse: {gen_result['parse_status']})")

        except Exception as e:
            print(f"  Generation failed: {e}")
            results.append({
                "target_id": target_id,
                "target_title": target_title,
                "error": f"generation_failed: {str(e)[:200]}",
                "timestamp": datetime.now().isoformat(),
            })
            continue

        # Check for target leakage in generation prompt
        predecessors_text = format_predecessors(record.get("predecessors", []))
        gen_prompt = GENERATION_PROMPT.format(
            predecessors_text=predecessors_text,
            synthesis_narrative=record.get("synthesis_narrative", ""),
        )
        leakage_issues = check_target_leakage(gen_prompt, target_title, target_contribution)

        # Judge ideas (uses target title and contribution)
        judgments = []
        hit = False
        for idea_idx, idea in enumerate(ideas):
            try:
                judgment = judge_idea(
                    idea, target_title, target_contribution,
                    model_id, sleep_seconds,
                )
                judgment["idea_index"] = idea_idx
                judgments.append(judgment)
                total_input_tokens += judgment.get("input_tokens") or 0
                total_output_tokens += judgment.get("output_tokens") or 0

                if judgment["parse_status"] == "ok":
                    judge_parse_ok += 1
                else:
                    judge_parse_fail += 1

                if judgment.get("match"):
                    hit = True
                    print(f"    Idea {idea_idx+1}: MATCH (confidence={judgment['confidence']:.2f})")

            except Exception as e:
                judgments.append({
                    "idea_index": idea_idx,
                    "match": False,
                    "confidence": 0.0,
                    "reason": str(e)[:200],
                    "parse_status": "error",
                })
                judge_parse_fail += 1
                print(f"    Idea {idea_idx+1}: judge error: {e}")

        if hit:
            total_hits += 1
            print(f"  HIT! ({total_hits}/{idx+1})")
        else:
            print(f"  MISS")

        # Save result
        target_result = {
            "target_id": target_id,
            "target_title": target_title,
            "target_contribution": target_contribution,
            "num_predecessors": len(record.get("predecessors", [])),
            "generated_ideas": ideas,
            "judgments": judgments,
            "hit": hit,
            "leakage_issues": leakage_issues,
            "generation": {
                "raw_output": gen_result["raw_output"][:2000],
                "parse_status": gen_result["parse_status"],
                "input_tokens": gen_result.get("input_tokens"),
                "output_tokens": gen_result.get("output_tokens"),
                "elapsed_seconds": gen_result.get("elapsed_seconds"),
                "finish_reason": gen_result.get("finish_reason"),
            },
            "timestamp": datetime.now().isoformat(),
        }
        results.append(target_result)

    # Compute summary
    completed = len(results)
    total_judgments = judge_parse_ok + judge_parse_fail
    generation_parse_rate = round(parse_ok / max(completed, 1) * 100, 1)
    judge_parse_rate = round(judge_parse_ok / max(total_judgments, 1) * 100, 1)
    hit_rate = round(total_hits / max(completed, 1) * 100, 1)

    # Check for any leakage across all targets
    any_leakage = any(r.get("leakage_issues") for r in results)

    # Save output
    output_path = output_dir / f"smoke_direct10_{model_slug}_selfjudge_3t_20260614.json"
    output = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "kind": "smoke_direct10_selfjudge_3t",
        "generator_model": model_id,
        "judge_model": model_id,
        "prompt_version": "baseline_v1_target_hidden",
        "criterion": "same_core_research_direction",
        "total_targets": len(records),
        "completed": completed,
        "hits": total_hits,
        "hit_at_10": hit_rate,
        "generation_parse_ok": parse_ok,
        "generation_parse_fail": parse_fail,
        "generation_parse_rate": generation_parse_rate,
        "judge_parse_ok": judge_parse_ok,
        "judge_parse_fail": judge_parse_fail,
        "judge_parse_rate": judge_parse_rate,
        "total_ideas": total_ideas,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "any_leakage_detected": any_leakage,
        "targets": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"Smoke Test Summary:")
    print(f"  Model: {model_id}")
    print(f"  Targets: {completed}/{len(records)}")
    print(f"  Hits: {total_hits} ({hit_rate}%)")
    print(f"  Generation parse rate: {generation_parse_rate}%")
    print(f"  Judge parse rate: {judge_parse_rate}%")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens:,}")
    print(f"  Any leakage: {any_leakage}")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
