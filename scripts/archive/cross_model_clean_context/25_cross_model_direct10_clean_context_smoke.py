#!/usr/bin/env python3
"""
Cross-model Direct-10 clean-context smoke test.

Uses ONLY predecessor paper titles for generation — no synthesis_narrative,
no predecessor role, no predecessor relationship_sentence.

Default smoke output:
  results/experiments/20260614_cross_model_zhiyuan1/smoke_direct10_<model_slug>_selfjudge_cleanctx_3t_20260614.json

For full clean generation with no self-judge, pass:
  --limit 77 --skip-self-judge --resume
"""

import json
import os
import re
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

logger = logging.getLogger(__name__)
_CHAT_COMPLETION = None

# CLEAN generation prompt: predecessor titles ONLY
GENERATION_PROMPT = """You are an expert AI researcher. Given the following set of predecessor papers that influenced a research direction, generate exactly 10 distinct research ideas that could advance this direction.

## Predecessor Papers

{predecessors_text}

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

STRICT_GENERATION_PROMPT = """You are an expert AI researcher. Given only the predecessor paper titles below, generate exactly 10 distinct research ideas that could advance this research direction.

## Predecessor Papers

{predecessors_text}

## Required JSON Schema

Return a valid JSON array with exactly 10 objects. Each object must have exactly these string fields:
- "idea_title"
- "idea_description"
- "key_innovation"
- "addressed_gap"

Formatting rules:
- Return raw JSON only.
- Do not use markdown code fences.
- Do not include comments.
- Do not use trailing commas.
- Escape any quotation marks inside string values.
- Keep each string concise.

Return ONLY the JSON array."""

# Judge prompt (sees target title and contribution — only after ideas are fixed)
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


def format_predecessors_clean(predecessors: list[dict]) -> str:
    """Format predecessors using titles ONLY — no role, no relationship_sentence."""
    lines = []
    for i, p in enumerate(predecessors, 1):
        title = p.get("title", "Unknown")
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


def safe_model_slug(model_id: str) -> str:
    """Create a safe model slug without importing the API client."""
    return model_id.lower().replace("/", "-").replace("_", "-").replace(".", "")


def get_model_id(arg_model: str | None, require: bool = True) -> str:
    """Get model id from CLI or env without importing the API client."""
    model = arg_model or os.environ.get("SJTU_MODEL_ID")
    if require and not model:
        raise RuntimeError("Set SJTU_MODEL_ID in environment or pass --model")
    return model or "dry-run-model"


def get_sleep_seconds() -> float:
    """Get sleep seconds without importing the API client."""
    return float(os.environ.get("SJTU_SLEEP_SECONDS", "0.5"))


def get_chat_completion():
    """Lazy-load the OpenAI-compatible client only for real API calls."""
    global _CHAT_COMPLETION
    if _CHAT_COMPLETION is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "openai_compatible_client",
            PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CHAT_COMPLETION = mod.chat_completion
    return _CHAT_COMPLETION


def parse_json_from_response(text: str):
    """Extract JSON from model response, handling markdown code blocks and common issues."""
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    def candidates(raw: str) -> list[str]:
        fixed = raw
        fixed = re.sub(r",\s*\]", "]", fixed)
        fixed = re.sub(r",\s*\}", "}", fixed)
        fixed = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", fixed)
        out = [raw, fixed]
        match = re.search(r"\[[\s\S]*\]", fixed)
        if match:
            out.append(match.group())
        match = re.search(r"\{[\s\S]*\}", fixed)
        if match:
            out.append(match.group())
        return out

    for candidate in candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def generate_ideas(record: dict, model: str, sleep_seconds: float, max_attempts: int = 2) -> dict:
    """Generate 10 ideas using clean context (predecessor titles only)."""
    predecessors_text = format_predecessors_clean(record.get("predecessors", []))
    attempts = []

    for attempt in range(1, max_attempts + 1):
        prompt_template = GENERATION_PROMPT if attempt == 1 else STRICT_GENERATION_PROMPT
        prompt = prompt_template.format(predecessors_text=predecessors_text)

        messages = [{"role": "user", "content": prompt}]
        result = get_chat_completion()(
            messages, model=model, provider="sjtu",
            temperature=0.7 if attempt == 1 else 0.2,
            max_tokens=4096,
            sleep_seconds=sleep_seconds,
        )

        raw_content = result["content"]
        parsed = parse_json_from_response(raw_content)

        ideas = []
        raw_idea_count = 0
        if isinstance(parsed, list):
            raw_idea_count = len(parsed)
            for item in parsed[:10]:
                if isinstance(item, dict):
                    ideas.append({
                        "idea_title": item.get("idea_title", ""),
                        "idea_description": item.get("idea_description", ""),
                        "key_innovation": item.get("key_innovation", ""),
                        "addressed_gap": item.get("addressed_gap", ""),
                    })

        parse_status = "ok" if len(ideas) == 10 else "parse_failed"
        attempt_record = {
            "attempt": attempt,
            "parse_status": parse_status,
            "raw_idea_count": raw_idea_count,
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "finish_reason": result.get("finish_reason"),
            "raw_output": raw_content[:2000],
            "raw_output_truncated": len(raw_content) > 2000,
        }
        if parse_status != "ok":
            attempt_record["raw_output_full_on_parse_fail"] = raw_content
        attempts.append(attempt_record)

        if parse_status == "ok":
            return {
                "raw_output": raw_content[:2000],
                "raw_output_truncated": len(raw_content) > 2000,
                "parsed_ideas": ideas,
                "parse_status": "ok",
                "raw_idea_count": raw_idea_count,
                "attempts": attempts,
                "input_tokens": sum(a.get("input_tokens") or 0 for a in attempts),
                "output_tokens": sum(a.get("output_tokens") or 0 for a in attempts),
                "elapsed_seconds": sum(a.get("elapsed_seconds") or 0 for a in attempts),
                "finish_reason": result.get("finish_reason"),
            }

    last = attempts[-1] if attempts else {}
    return {
        "raw_output": last.get("raw_output", ""),
        "raw_output_truncated": last.get("raw_output_truncated", False),
        "parsed_ideas": [],
        "parse_status": "parse_failed",
        "raw_idea_count": last.get("raw_idea_count", 0),
        "attempts": attempts,
        "input_tokens": sum(a.get("input_tokens") or 0 for a in attempts),
        "output_tokens": sum(a.get("output_tokens") or 0 for a in attempts),
        "elapsed_seconds": sum(a.get("elapsed_seconds") or 0 for a in attempts),
        "finish_reason": last.get("finish_reason"),
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
    result = get_chat_completion()(
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


def verify_clean_context(record: dict) -> list[str]:
    """Verify that rendered generation prompt contains no target-derived text."""
    issues = []
    # Build the actual prompt
    predecessors_text = format_predecessors_clean(record.get("predecessors", []))
    prompt = GENERATION_PROMPT.format(predecessors_text=predecessors_text)

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    def contains_full_field(field_value: str, min_chars: int = 12) -> bool:
        """Check full-field inclusion; avoids short-prefix false positives."""
        field = norm(field_value)
        if len(field) < min_chars:
            return False
        return field in norm(prompt)

    # Check full target-derived fields in the rendered prompt. Predecessor titles
    # are allowed by construction; roles/relationships are not.
    if contains_full_field(record.get("title", "")):
        issues.append("target_title_in_prompt")
    if contains_full_field(record.get("contribution", "")):
        issues.append("target_contribution_in_prompt")
    if contains_full_field(record.get("abstract", ""), min_chars=40):
        issues.append("target_abstract_in_prompt")
    if contains_full_field(record.get("synthesis_narrative", ""), min_chars=40):
        issues.append("synthesis_narrative_in_prompt")

    for p in record.get("predecessors", []):
        if contains_full_field(p.get("role", "")):
            issues.append(f"predecessor_role_in_prompt: {p.get('title', '')[:30]}")
            break

    for p in record.get("predecessors", []):
        if contains_full_field(p.get("relationship_sentence", ""), min_chars=30):
            issues.append(f"relationship_sentence_in_prompt: {p.get('title', '')[:30]}")
            break

    for p in record.get("predecessors", []):
        if contains_full_field(p.get("synthesis_narrative", ""), min_chars=40):
            issues.append(f"predecessor_synthesis_narrative_in_prompt: {p.get('title', '')[:30]}")
            break

    for key in ["primary_pattern", "pattern_reasoning"]:
        if contains_full_field(str(record.get(key, "")), min_chars=20):
            issues.append(f"{key}_in_prompt")

    for pattern in record.get("secondary_patterns", []) or []:
        if contains_full_field(str(pattern), min_chars=20):
            issues.append("secondary_pattern_in_prompt")
            break

    return issues


def main():
    parser = argparse.ArgumentParser(description="Cross-model Direct-10 clean-context smoke test")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1"))
    parser.add_argument("--model", help="Model ID (overrides SJTU_MODEL_ID env)")
    parser.add_argument("--limit", type=int, default=3, help="Number of targets")
    parser.add_argument("--sleep-seconds", type=float, help="Sleep between calls")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--resume", action="store_true", help="Resume from existing output")
    parser.add_argument("--skip-self-judge", action="store_true", help="Generate only; do not run ZhiYuan self-judge")
    parser.add_argument("--max-generation-attempts", type=int, default=2, help="Generation attempts per target")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without API calls")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get model ID
    try:
        model_id = get_model_id(args.model)
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

    scope = f"{len(records)}t"
    if args.output:
        output_path = Path(args.output)
    elif args.skip_self_judge:
        output_path = output_dir / f"generation_direct10_{model_slug}_targethidden-cleanctx_{scope}_20260614.json"
    elif len(records) == 3:
        output_path = output_dir / f"smoke_direct10_{model_slug}_selfjudge_cleanctx_3t_20260614.json"
    else:
        output_path = output_dir / f"direct10_{model_slug}_selfjudge_cleanctx_{scope}_20260614.json"

    # Verify clean context for all targets
    print("\n=== Context Verification ===")
    all_clean = True
    for i, rec in enumerate(records):
        issues = verify_clean_context(rec)
        if issues:
            print(f"  [{i+1}] {rec['target_id']}: ISSUES: {issues}")
            all_clean = False
        else:
            print(f"  [{i+1}] {rec['target_id']}: CLEAN")

    if not all_clean:
        print("\nERROR: Some records have target-derived fields. Do not proceed.")
        return 1

    print("\nAll records verified clean — no target-derived bridge fields.")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for i, rec in enumerate(records):
            predecessors_text = format_predecessors_clean(rec.get("predecessors", []))
            prompt = GENERATION_PROMPT.format(predecessors_text=predecessors_text)
            print(f"\n  [{i+1}] {rec['target_id']}: {rec.get('title', '')[:60]}")
            print(f"    Prompt length: {len(prompt)} chars")
            print(f"    Predecessors: {len(rec.get('predecessors', []))}")
            # Verify no target title/contribution in prompt
            target_title = rec.get("title", "")
            target_contribution = rec.get("contribution", "")
            if target_title.lower() in prompt.lower():
                print(f"    WARNING: target title in prompt!")
            elif target_contribution and target_contribution.lower() in prompt.lower():
                print(f"    WARNING: target contribution in prompt!")
            else:
                print(f"    No target leakage detected")
        print("\nDry run complete; no API calls made.")
        return 0

    # Run clean smoke/full experiment
    results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_ideas = 0
    parse_ok = 0
    parse_fail = 0
    judge_parse_ok = 0
    judge_parse_fail = 0
    total_hits = 0
    completed_ids = set()
    superseded_incomplete_targets = []
    superseded_input_tokens = 0
    superseded_output_tokens = 0

    def is_complete_result(result: dict) -> bool:
        return (
            result.get("generation", {}).get("parse_status") == "ok"
            and len(result.get("generated_ideas", [])) == 10
            and not result.get("leakage_issues")
        )

    def sanitize_generation_only_result(result: dict) -> dict:
        """Remove target-visible fields from generation-only artifacts."""
        if not args.skip_self_judge:
            return result
        cleaned = dict(result)
        cleaned.pop("target_title", None)
        cleaned.pop("target_contribution", None)
        cleaned.pop("contribution_source", None)
        cleaned["target_visible_metadata_stored"] = False
        return cleaned

    def recompute_totals(current_results: list[dict]):
        input_tokens = superseded_input_tokens
        output_tokens = superseded_output_tokens
        idea_count = 0
        gen_ok = 0
        gen_fail = 0
        judge_ok = 0
        judge_fail = 0
        hits = 0
        for r in current_results:
            gen = r.get("generation", {})
            input_tokens += gen.get("input_tokens") or 0
            output_tokens += gen.get("output_tokens") or 0
            idea_count += len(r.get("generated_ideas", []))
            if gen.get("parse_status") == "ok":
                gen_ok += 1
            else:
                gen_fail += 1
            if r.get("hit") is True:
                hits += 1
            for j in r.get("judgments", []):
                input_tokens += j.get("input_tokens") or 0
                output_tokens += j.get("output_tokens") or 0
                if j.get("parse_status") == "ok":
                    judge_ok += 1
                elif j.get("parse_status"):
                    judge_fail += 1
        return input_tokens, output_tokens, idea_count, gen_ok, gen_fail, judge_ok, judge_fail, hits

    if args.resume and output_path.exists():
        with open(output_path) as f:
            existing = json.load(f)
        existing_results = existing.get("targets", [])
        results = [sanitize_generation_only_result(r) for r in existing_results if is_complete_result(r)]
        incomplete = [r for r in existing_results if not is_complete_result(r)]
        superseded_incomplete_targets = [
            {
                "target_id": r.get("target_id"),
                "parse_status": r.get("generation", {}).get("parse_status"),
                "idea_count": len(r.get("generated_ideas", [])),
            }
            for r in incomplete
        ]
        superseded_input_tokens = existing.get("superseded_incomplete_attempt_input_tokens", 0) or 0
        superseded_output_tokens = existing.get("superseded_incomplete_attempt_output_tokens", 0) or 0
        for r in incomplete:
            gen = r.get("generation", {})
            superseded_input_tokens += gen.get("input_tokens") or 0
            superseded_output_tokens += gen.get("output_tokens") or 0
        completed_ids = {r["target_id"] for r in results if "target_id" in r}
        (
            total_input_tokens,
            total_output_tokens,
            total_ideas,
            parse_ok,
            parse_fail,
            judge_parse_ok,
            judge_parse_fail,
            total_hits,
        ) = recompute_totals(results)
        print(f"Resuming: {len(completed_ids)} complete targets loaded from {output_path}")
        if incomplete:
            print(f"Will rerun {len(incomplete)} incomplete/failed targets")

    remaining = [r for r in records if r["target_id"] not in completed_ids]

    def write_checkpoint():
        completed = len(results)
        total_judgments = judge_parse_ok + judge_parse_fail
        generation_parse_rate = round(parse_ok / max(completed, 1) * 100, 1)
        judge_parse_rate = None if args.skip_self_judge else round(judge_parse_ok / max(total_judgments, 1) * 100, 1)
        hit_rate = None if args.skip_self_judge else round(total_hits / max(completed, 1) * 100, 1)
        any_leakage = any(r.get("leakage_issues") for r in results)

        output = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "kind": "generation_direct10_cleanctx" if args.skip_self_judge else "direct10_selfjudge_cleanctx",
            "generator_model": model_id,
            "judge_model": None if args.skip_self_judge else model_id,
            "prompt_version": "clean_predecessor_titles_only",
            "criterion": None if args.skip_self_judge else "same_core_research_direction",
            "context_mode": "clean",
            "context_description": "Predecessor titles only; no synthesis_narrative, no role, no relationship_sentence",
            "total_targets": len(records),
            "completed": completed,
            "hits": None if args.skip_self_judge else total_hits,
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
            "superseded_incomplete_attempt_input_tokens": superseded_input_tokens,
            "superseded_incomplete_attempt_output_tokens": superseded_output_tokens,
            "superseded_incomplete_targets": superseded_incomplete_targets,
            "any_leakage_detected": any_leakage,
            "targets": results,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    for idx, record in enumerate(remaining):
        target_id = record["target_id"]
        target_title = record.get("title", "")
        target_contribution = record.get("contribution", "")

        print(f"\n[{idx+1}/{len(remaining)}] {target_id}: {target_title[:60]}...")

        # Generate ideas (clean context)
        try:
            gen_result = generate_ideas(
                record,
                model_id,
                sleep_seconds,
                max_attempts=max(args.max_generation_attempts, 1),
            )
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

        # Judge ideas unless this is a generation-only full run
        judgments = []
        hit = None if args.skip_self_judge else False
        if args.skip_self_judge:
            print("  Self-judge skipped")
        else:
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
                print(f"  HIT! ({total_hits}/{len(results) + 1})")
            else:
                print(f"  MISS")

        # Save result
        target_result = {
            "target_id": target_id,
            "num_predecessors": len(record.get("predecessors", [])),
            "generated_ideas": ideas,
            "judgments": judgments,
            "hit": hit,
            "leakage_issues": [],
            "target_visible_metadata_stored": False if args.skip_self_judge else True,
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
        if not args.skip_self_judge:
            target_result["target_title"] = target_title
            target_result["target_contribution"] = target_contribution
        results.append(target_result)
        write_checkpoint()
        print(f"  Checkpoint saved: {output_path}")

    # Compute summary
    completed = len(results)
    total_judgments = judge_parse_ok + judge_parse_fail
    generation_parse_rate = round(parse_ok / max(completed, 1) * 100, 1)
    judge_parse_rate = None if args.skip_self_judge else round(judge_parse_ok / max(total_judgments, 1) * 100, 1)
    hit_rate = None if args.skip_self_judge else round(total_hits / max(completed, 1) * 100, 1)
    any_leakage = any(r.get("leakage_issues") for r in results)

    write_checkpoint()
    print(f"\nSaved: {output_path}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"Clean-Context Smoke Test Summary:")
    print(f"  Model: {model_id}")
    print(f"  Targets: {completed}/{len(records)}")
    if args.skip_self_judge:
        print("  Self-judge: skipped")
    else:
        print(f"  Hits: {total_hits} ({hit_rate}%)")
    print(f"  Generation parse rate: {generation_parse_rate}%")
    print(f"  Judge parse rate: {judge_parse_rate if judge_parse_rate is not None else 'N/A'}")
    print(f"  Total tokens: {total_input_tokens + total_output_tokens:,}")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
