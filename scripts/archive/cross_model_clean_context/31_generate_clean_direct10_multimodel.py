#!/usr/bin/env python3
"""
Generate clean-context Direct-10 ideas with MiMo or SJTU-hosted models.

Generation prompt uses predecessor titles only. Target title, target
contribution, target abstract, synthesis narrative, predecessor role, and
predecessor-target relationship text are not included in the generation prompt.

This script does not judge ideas.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "results" / "experiments" / "20260614_multimodel_matrix"
DEFAULT_INPUT = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"

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


def safe_model_slug(model_id: str) -> str:
    return model_id.lower().replace("/", "-").replace("_", "-").replace(".", "")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def format_predecessors_clean(predecessors: list[dict]) -> str:
    return "\n".join(f"{idx}. {p.get('title', 'Unknown')}" for idx, p in enumerate(predecessors, 1))


def parse_json_from_response(text: str):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()

    fixed = re.sub(r",\s*\]", "]", text)
    fixed = re.sub(r",\s*\}", "}", fixed)
    fixed = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", fixed)
    candidates = [text, fixed]
    match = re.search(r"\[[\s\S]*\]", fixed)
    if match:
        candidates.append(match.group())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None


def load_sjtu_chat_completion():
    spec = importlib.util.spec_from_file_location(
        "openai_compatible_client",
        PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.chat_completion


def load_mimo_chat_completion():
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from mimo_client import chat_completion

    return chat_completion


def call_chat(provider: str, model: str, messages: list[dict], temperature: float, max_tokens: int, sleep_seconds: float) -> dict:
    if provider == "sjtu":
        return load_sjtu_chat_completion()(
            messages,
            model=model,
            provider="sjtu",
            temperature=temperature,
            max_tokens=max_tokens,
            sleep_seconds=sleep_seconds,
        )
    if provider == "mimo":
        return load_mimo_chat_completion()(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            sleep_seconds=sleep_seconds,
        )
    raise ValueError(f"Unknown provider: {provider}")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def contains_full_field(prompt: str, value: str, min_chars: int = 12) -> bool:
    value_norm = norm(value)
    if len(value_norm) < min_chars:
        return False
    return value_norm in norm(prompt)


def verify_clean_context(record: dict) -> list[str]:
    predecessors_text = format_predecessors_clean(record.get("predecessors", []))
    prompt = GENERATION_PROMPT.format(predecessors_text=predecessors_text)
    issues = []
    if contains_full_field(prompt, record.get("title", "")):
        issues.append("target_title_in_prompt")
    if contains_full_field(prompt, record.get("contribution", ""), min_chars=20):
        issues.append("target_contribution_in_prompt")
    if contains_full_field(prompt, record.get("abstract", ""), min_chars=40):
        issues.append("target_abstract_in_prompt")
    if contains_full_field(prompt, record.get("synthesis_narrative", ""), min_chars=40):
        issues.append("synthesis_narrative_in_prompt")
    for pred in record.get("predecessors", []):
        if contains_full_field(prompt, pred.get("role", ""), min_chars=20):
            issues.append(f"predecessor_role_in_prompt:{pred.get('title', '')[:40]}")
            break
    for pred in record.get("predecessors", []):
        if contains_full_field(prompt, pred.get("relationship_sentence", ""), min_chars=30):
            issues.append(f"relationship_sentence_in_prompt:{pred.get('title', '')[:40]}")
            break
    return issues


def generate_ideas(provider: str, model: str, sleep_seconds: float, record: dict, max_attempts: int) -> dict:
    predecessors_text = format_predecessors_clean(record.get("predecessors", []))
    attempts = []
    for attempt in range(1, max_attempts + 1):
        prompt_template = GENERATION_PROMPT if attempt == 1 else STRICT_GENERATION_PROMPT
        prompt = prompt_template.format(predecessors_text=predecessors_text)
        result = call_chat(
            provider,
            model,
            [{"role": "user", "content": prompt}],
            temperature=0.7 if attempt == 1 else 0.2,
            max_tokens=4096,
            sleep_seconds=sleep_seconds,
        )
        raw = result.get("content", "")
        parsed = parse_json_from_response(raw)
        ideas = []
        raw_idea_count = 0
        if isinstance(parsed, list):
            raw_idea_count = len(parsed)
            for item in parsed[:10]:
                if isinstance(item, dict):
                    ideas.append(
                        {
                            "idea_title": str(item.get("idea_title", "")),
                            "idea_description": str(item.get("idea_description", "")),
                            "key_innovation": str(item.get("key_innovation", "")),
                            "addressed_gap": str(item.get("addressed_gap", "")),
                        }
                    )
        parse_status = "ok" if len(ideas) == 10 else "parse_failed"
        attempt_record = {
            "attempt": attempt,
            "parse_status": parse_status,
            "raw_idea_count": raw_idea_count,
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "finish_reason": result.get("finish_reason"),
            "raw_output": raw[:2000],
            "raw_output_truncated": len(raw) > 2000,
        }
        if parse_status != "ok":
            attempt_record["raw_output_full_on_parse_fail"] = raw
        attempts.append(attempt_record)
        if parse_status == "ok":
            return {
                "parse_status": "ok",
                "parsed_ideas": ideas,
                "raw_idea_count": raw_idea_count,
                "attempts": attempts,
                "input_tokens": sum(a.get("input_tokens") or 0 for a in attempts),
                "output_tokens": sum(a.get("output_tokens") or 0 for a in attempts),
                "elapsed_seconds": sum(a.get("elapsed_seconds") or 0 for a in attempts),
                "finish_reason": result.get("finish_reason"),
            }

    return {
        "parse_status": "parse_failed",
        "parsed_ideas": [],
        "raw_idea_count": attempts[-1].get("raw_idea_count", 0) if attempts else 0,
        "attempts": attempts,
        "input_tokens": sum(a.get("input_tokens") or 0 for a in attempts),
        "output_tokens": sum(a.get("output_tokens") or 0 for a in attempts),
        "elapsed_seconds": sum(a.get("elapsed_seconds") or 0 for a in attempts),
        "finish_reason": attempts[-1].get("finish_reason") if attempts else None,
    }


def load_records(path: Path, limit: int | None) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records[:limit] if limit else records


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate clean-context Direct-10 ideas with one model")
    parser.add_argument("--provider", required=True, choices=["mimo", "sjtu"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(EXP_DIR))
    parser.add_argument("--output")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--max-generation-attempts", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = load_records(Path(args.input), args.limit)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_slug = f"{args.provider}-{safe_model_slug(args.model)}"
    output_path = Path(args.output) if args.output else output_dir / f"generation_direct10_{model_slug}_targethidden-cleanctx_{len(records)}t_20260614.json"

    print(f"Provider/model: {args.provider}/{args.model}")
    print(f"Targets: {len(records)}")
    print(f"Output: {output_path}")

    all_issues = {}
    for record in records:
        issues = verify_clean_context(record)
        if issues:
            all_issues[record["target_id"]] = issues
    if all_issues:
        print("CLEAN CONTEXT VERIFICATION FAILED:")
        for target_id, issues in list(all_issues.items())[:20]:
            print(f"  - {target_id}: {issues}")
        return 1

    if args.dry_run:
        print("Dry run complete; no API calls made.")
        for record in records[:3]:
            prompt = GENERATION_PROMPT.format(predecessors_text=format_predecessors_clean(record.get("predecessors", [])))
            print(f"  {record['target_id']}: predecessors={len(record.get('predecessors', []))}, prompt_chars={len(prompt)}")
        return 0

    results = []
    completed_ids = set()
    superseded_input_tokens = 0
    superseded_output_tokens = 0
    superseded_incomplete_targets = []
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text())
        seen = set()
        for target in existing.get("targets", []):
            target_id = target.get("target_id")
            complete = (
                target_id
                and target_id not in seen
                and target.get("generation", {}).get("parse_status") == "ok"
                and len(target.get("generated_ideas", [])) == 10
                and not target.get("leakage_issues")
            )
            if complete:
                results.append(target)
                seen.add(target_id)
            else:
                gen = target.get("generation", {})
                superseded_input_tokens += gen.get("input_tokens") or 0
                superseded_output_tokens += gen.get("output_tokens") or 0
                superseded_incomplete_targets.append(
                    {
                        "target_id": target_id,
                        "parse_status": gen.get("parse_status"),
                        "idea_count": len(target.get("generated_ideas", [])),
                    }
                )
        completed_ids = seen
        print(f"Resuming: {len(results)} complete targets")
        if superseded_incomplete_targets:
            print(f"Will rerun {len(superseded_incomplete_targets)} incomplete targets")

    def recompute():
        input_tokens = superseded_input_tokens
        output_tokens = superseded_output_tokens
        parse_ok = 0
        parse_fail = 0
        total_ideas = 0
        any_leakage = False
        for target in results:
            gen = target.get("generation", {})
            input_tokens += gen.get("input_tokens") or 0
            output_tokens += gen.get("output_tokens") or 0
            total_ideas += len(target.get("generated_ideas", []))
            if gen.get("parse_status") == "ok":
                parse_ok += 1
            else:
                parse_fail += 1
            if target.get("leakage_issues"):
                any_leakage = True
        completed = len(results)
        return {
            "completed": completed,
            "generation_parse_ok": parse_ok,
            "generation_parse_fail": parse_fail,
            "generation_parse_rate": round(parse_ok / max(completed, 1) * 100, 1),
            "total_ideas": total_ideas,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "any_leakage_detected": any_leakage,
        }

    def write_checkpoint():
        metrics = recompute()
        output = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "kind": "generation_direct10_cleanctx",
            "generator_provider": args.provider,
            "generator_model": args.model,
            "prompt_version": "clean_predecessor_titles_only_v1",
            "context_mode": "clean",
            "context_description": "Predecessor titles only; target title/contribution/abstract/synthesis/roles/relationships excluded",
            "input_file": display_path(Path(args.input)),
            "total_targets": len(records),
            **metrics,
            "superseded_incomplete_attempt_input_tokens": superseded_input_tokens,
            "superseded_incomplete_attempt_output_tokens": superseded_output_tokens,
            "superseded_incomplete_targets": superseded_incomplete_targets,
            "targets": results,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    remaining = [record for record in records if record["target_id"] not in completed_ids]
    for idx, record in enumerate(remaining, 1):
        target_id = record["target_id"]
        print(f"\n[{idx}/{len(remaining)}] {target_id}")
        leakage_issues = verify_clean_context(record)
        if leakage_issues:
            result = {
                "target_id": target_id,
                "num_predecessors": len(record.get("predecessors", [])),
                "generated_ideas": [],
                "judgments": [],
                "hit": None,
                "leakage_issues": leakage_issues,
                "generation": {"parse_status": "skipped_leakage"},
                "target_visible_metadata_stored": False,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            gen = generate_ideas(
                args.provider,
                args.model,
                args.sleep_seconds,
                record,
                max(args.max_generation_attempts, 1),
            )
            result = {
                "target_id": target_id,
                "num_predecessors": len(record.get("predecessors", [])),
                "generated_ideas": gen.get("parsed_ideas", []),
                "judgments": [],
                "hit": None,
                "leakage_issues": [],
                "generation": {k: v for k, v in gen.items() if k != "parsed_ideas"},
                "target_visible_metadata_stored": False,
                "timestamp": datetime.now().isoformat(),
            }
        results.append(result)
        write_checkpoint()
        print(f"  ideas={len(result['generated_ideas'])} status={result['generation'].get('parse_status')}")

    write_checkpoint()
    metrics = recompute()
    print("\nGeneration complete")
    print(f"Targets: {metrics['completed']}/{len(records)}")
    print(f"Ideas: {metrics['total_ideas']}")
    print(f"Parse rate: {metrics['generation_parse_rate']}%")
    print(f"Leakage detected: {metrics['any_leakage_detected']}")
    print(f"Output: {output_path}")
    return 0 if metrics["completed"] == len(records) and metrics["total_ideas"] == len(records) * 10 and not metrics["any_leakage_detected"] else 1


if __name__ == "__main__":
    sys.exit(main())
