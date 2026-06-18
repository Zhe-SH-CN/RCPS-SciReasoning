#!/usr/bin/env python3
"""
Sci-Reasoning-aligned Direct/rejudge runner.

This script resets evaluation around the paper/repository protocol instead of
the older local "same core research direction" prompt.

Modes:
- direct: generate 10 ideas from predecessor paper contents, then judge them.
- rejudge: judge an existing fixed final-idea set with the same judge prompt.

Protocol modes:
- paper_json: Appendix-B.4-style JSON judge: is_match/confidence/reasoning.
- repo_binary: official repository v4 Exa MATCH/NO_MATCH judge.

The predecessor context comes from the local Sci-Reasoning author-repository
result cache, which stores Exa-retrieved predecessor paper contents for all 77
NeurIPS 2025 Oral targets used by the reset experiments. This avoids live
retrieval drift while keeping generation grounded in predecessor paper content.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_DATA = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
DEFAULT_CONTEXT_CACHE = (
    PROJECT_ROOT
    / "Sci-Reasoning"
    / "research_idea_evaluation"
    / "results"
    / "evaluation_results_claude_sonnet_final.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "20260615_scireasoning_faithful"

SOURCE_DEFAULTS = {
    "direct10_mimo_legacy": PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json",
    "bcs50_mimo_legacy": PROJECT_ROOT / "results" / "bcs50_eval_mimo_v25pro.json",
    "pgcr_mimo_legacy": PROJECT_ROOT / "results" / "pgcr_enriched_eval.json",
}

SOURCE_IDEA_FIELDS = {
    "direct10_mimo_legacy": "generated_ideas",
    "bcs50_mimo_legacy": "selected_ideas",
    "pgcr_mimo_legacy": "selected_ideas",
    "direct_output": "generated_ideas",
}

GENERATION_PROMPT = """You are a research scientist analyzing recent papers to identify promising research directions.

Based on the following papers, generate exactly {k} novel research ideas that could naturally follow from this body of work. Each idea should:
1. Build upon concepts, methods, or findings from these papers
2. Be specific and actionable (not vague)
3. Represent a meaningful contribution to the field

Papers:
{context}

Generate exactly {k} research ideas. For each idea, provide:
- A concise title (1 line)
- A brief description of the key contribution (2-3 sentences)

Format your response as a numbered list (1-{k})."""

PAPER_JSON_SYSTEM = "You are an expert at evaluating research paper similarity. Always respond with valid JSON."

PAPER_JSON_JUDGE_PROMPT = """You are evaluating whether a generated research idea matches a real published paper.

GENERATED IDEA:
Title: {idea_title}
Description: {idea_description}

REAL PUBLISHED PAPER:
Title: {ground_truth_title}
Contribution: {ground_truth_contribution}

Determine if the generated idea is semantically similar to the real paper. Consider:
1. Do they address the same core problem or research question?
2. Do they propose similar methodological approaches?
3. Would the generated idea, if fully developed, result in a similar contribution?

A match means the ideas are substantially aligned in their core direction, not necessarily identical in every detail.

Respond with a JSON object containing:
- "is_match": true or false
- "confidence": a number from 0 to 1
- "reasoning": a brief explanation (2-3 sentences)

Output ONLY the JSON object, no other text."""

REPO_BINARY_JUDGE_PROMPT = """You are evaluating whether a generated research idea matches a real published paper.

Generated Idea:
{idea_text}

Real Published Paper:
Title: {ground_truth_title}
Contribution: {ground_truth_contribution}

Does the generated idea capture the same core concept, approach, or contribution as the real paper?
Consider semantic similarity, not exact wording. The idea should address the same problem with a similar approach.

Respond with ONLY one of:
- "MATCH" if the generated idea substantially aligns with the real paper's core contribution
- "NO_MATCH" if they are about different topics or approaches"""


def safe_model_slug(model_id: str) -> str:
    return model_id.lower().replace("/", "-").replace("_", "-").replace(".", "")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def load_eval_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open() as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_context_cache(path: Path) -> dict[str, list[dict[str, Any]]]:
    obj = load_json(path)
    cache = {}
    for record in obj.get("results", []):
        title = record.get("paper_title")
        details = record.get("predecessor_details") or []
        if title and details:
            cache[title] = details
    return cache


def predecessor_titles(record: dict[str, Any]) -> list[str]:
    titles = []
    for pred in record.get("predecessors", []):
        if isinstance(pred, dict):
            title = str(pred.get("title") or "").strip()
        else:
            title = str(pred).strip()
        if title:
            titles.append(title)
    return titles


def build_context(
    predecessor_details: list[dict[str, Any]],
    max_chars_per_paper: int,
    target_title: str = "",
    target_contribution: str = "",
    exclude_target_text_context: bool = True,
) -> tuple[str, dict[str, Any]]:
    parts = []
    usable = 0
    excluded_target_title = 0
    excluded_target_contribution = 0
    quality = Counter()
    target_title_l = target_title.lower()
    target_contribution_l = target_contribution.lower()
    for idx, pred in enumerate(predecessor_details, 1):
        content = pred.get("content") or ""
        if not pred.get("success") or len(content) < 300:
            continue
        combined = " ".join([str(pred.get("title") or ""), str(pred.get("url") or ""), content]).lower()
        if exclude_target_text_context and target_title_l and target_title_l in combined:
            excluded_target_title += 1
            continue
        if exclude_target_text_context and len(target_contribution_l) > 60 and target_contribution_l in combined:
            excluded_target_contribution += 1
            continue
        usable += 1
        quality[pred.get("content_quality", "unknown")] += 1
        title = pred.get("title") or pred.get("original_query") or f"Paper {idx}"
        parts.append(f"=== Paper {idx}: {title} ===\n{content[:max_chars_per_paper]}\n")
    return "\n".join(parts), {
        "cache_predecessors": len(predecessor_details),
        "usable_predecessors": usable,
        "excluded_target_title_contexts": excluded_target_title,
        "excluded_target_contribution_contexts": excluded_target_contribution,
        "content_quality_counts": dict(quality),
        "max_chars_per_paper": max_chars_per_paper,
    }


def parse_json_response(text: str) -> Any:
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()
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
                recovered = recover_paper_json_judgment(match.group())
                if recovered is not None:
                    return recovered
    return None


def recover_paper_json_judgment(text: str) -> dict[str, Any] | None:
    """Recover MiMo outputs with valid fields but an unquoted reasoning string."""
    match_field = re.search(r'"is_match"\s*:\s*(true|false)\b', text, flags=re.IGNORECASE)
    confidence_field = re.search(r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
    if not match_field or not confidence_field:
        return None

    reasoning = ""
    reasoning_field = re.search(r'"reasoning"\s*:\s*([\s\S]*?)\s*\}\s*$', text)
    if reasoning_field:
        reasoning = reasoning_field.group(1).strip()
        reasoning = re.sub(r",\s*$", "", reasoning).strip()
        if reasoning.startswith('"'):
            try:
                reasoning = json.loads(reasoning)
            except json.JSONDecodeError:
                reasoning = reasoning.strip('"')
        else:
            reasoning = reasoning.strip('"')

    return {
        "is_match": match_field.group(1).lower() == "true",
        "confidence": float(confidence_field.group(1)),
        "reasoning": str(reasoning),
        "_recovered_parse": True,
    }


def parse_numbered_ideas(response_text: str, k: int) -> list[dict[str, str]]:
    text = response_text or ""
    ideas: list[dict[str, str]] = []
    pattern = r"(?:^|\n)\s*(\d+)[\.\)]\s*(.*?)(?=\n\s*\d+[\.\)]\s+|\Z)"
    for match in re.finditer(pattern, text, flags=re.DOTALL):
        body = match.group(2).strip()
        if len(body) < 20:
            continue
        lines = [line.strip(" -*") for line in body.splitlines() if line.strip()]
        title = lines[0] if lines else body[:120]
        description = " ".join(lines[1:]).strip() if len(lines) > 1 else body
        ideas.append(
            {
                "idea_title": title[:240],
                "idea_description": description[:4000],
                "idea_text": body[:5000],
            }
        )
    if not ideas:
        parts = re.split(r"\n\s*\d+[\.\)]\s*", text)
        for part in parts:
            part = part.strip()
            if len(part) > 20:
                ideas.append(
                    {
                        "idea_title": part.splitlines()[0][:240],
                        "idea_description": part[:4000],
                        "idea_text": part[:5000],
                    }
                )
    return ideas[:k]


def idea_to_text(idea: dict[str, Any]) -> tuple[str, str, str]:
    title = str(idea.get("idea_title") or idea.get("title") or "").strip()
    description = str(
        idea.get("idea_description")
        or idea.get("description")
        or idea.get("key_innovation")
        or idea.get("addressed_gap")
        or idea.get("idea_text")
        or ""
    ).strip()
    pieces = []
    if title:
        pieces.append(title)
    if description:
        pieces.append(description)
    if idea.get("key_innovation"):
        pieces.append(f"Key Innovation: {idea.get('key_innovation')}")
    if idea.get("addressed_gap"):
        pieces.append(f"Addressed Gap: {idea.get('addressed_gap')}")
    return title, description, "\n".join(pieces).strip()


def load_chat_function(provider: str):
    if provider == "mimo":
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from mimo_client import chat_completion

        return chat_completion
    if provider == "sjtu":
        spec = importlib.util.spec_from_file_location(
            "openai_compatible_client",
            PROJECT_ROOT / "scripts" / "22_openai_compatible_client.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def _chat(messages, model, temperature, max_tokens, sleep_seconds):
            return mod.chat_completion(
                messages,
                model=model,
                provider="sjtu",
                temperature=temperature,
                max_tokens=max_tokens,
                sleep_seconds=sleep_seconds,
            )

        return _chat
    raise ValueError(f"Unknown provider: {provider}")


def call_chat(provider: str, model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int, sleep_seconds: float) -> dict[str, Any]:
    chat = load_chat_function(provider)
    if provider == "mimo":
        return chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, sleep_seconds=sleep_seconds)
    return chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, sleep_seconds=sleep_seconds)


def judge_idea(
    provider: str,
    model: str,
    protocol: str,
    idea: dict[str, Any],
    target_title: str,
    target_contribution: str,
    temperature: float,
    max_tokens: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    idea_title, idea_description, idea_text = idea_to_text(idea)
    if protocol == "paper_json":
        prompt = PAPER_JSON_JUDGE_PROMPT.format(
            idea_title=idea_title,
            idea_description=idea_description,
            ground_truth_title=target_title,
            ground_truth_contribution=target_contribution,
        )
        messages = [{"role": "system", "content": PAPER_JSON_SYSTEM}, {"role": "user", "content": prompt}]
    elif protocol == "repo_binary":
        prompt = REPO_BINARY_JUDGE_PROMPT.format(
            idea_text=idea_text,
            ground_truth_title=target_title,
            ground_truth_contribution=target_contribution,
        )
        messages = [{"role": "user", "content": prompt}]
    else:
        raise ValueError(f"Unknown protocol: {protocol}")

    try:
        result = call_chat(provider, model, messages, temperature, max_tokens, sleep_seconds)
    except Exception as exc:
        return {
            "is_match": False,
            "confidence": 0.0,
            "reasoning": str(exc)[:500],
            "raw_response": "",
            "parse_status": "api_error",
            "input_tokens": None,
            "output_tokens": None,
            "finish_reason": None,
        }

    raw = result.get("content") or ""
    judgment = {
        "is_match": False,
        "confidence": 0.0,
        "reasoning": "",
        "raw_response": raw,
        "parse_status": "parse_error",
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "finish_reason": result.get("finish_reason"),
    }

    if protocol == "paper_json":
        parsed = parse_json_response(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("is_match"), bool):
            judgment["is_match"] = parsed["is_match"]
            judgment["confidence"] = float(parsed.get("confidence", 0.0) or 0.0)
            judgment["reasoning"] = str(parsed.get("reasoning", ""))[:1200]
            judgment["parse_status"] = "ok"
            if parsed.get("_recovered_parse"):
                judgment["recovered_parse"] = True
        elif not raw:
            judgment["parse_status"] = "empty_response"
    else:
        normalized = raw.strip().upper()
        if "NO_MATCH" in normalized:
            judgment["is_match"] = False
            judgment["parse_status"] = "ok"
        elif "MATCH" in normalized:
            judgment["is_match"] = True
            judgment["parse_status"] = "ok"
        elif not raw:
            judgment["parse_status"] = "empty_response"
        judgment["reasoning"] = normalized[:200]
    return judgment


def recompute(records: list[dict[str, Any]]) -> dict[str, Any]:
    parse_counts = Counter()
    gen_counts = Counter()
    hits = 0
    input_tokens = 0
    output_tokens = 0
    total_judgments = 0
    excluded_target_title = 0
    excluded_target_contribution = 0
    for record in records:
        hit = any(j.get("is_match") is True for j in record.get("judgments", []))
        record["hit_at_k"] = hit
        if hit:
            hits += 1
        excluded_target_title += record.get("context_metadata", {}).get("excluded_target_title_contexts", 0)
        excluded_target_contribution += record.get("context_metadata", {}).get("excluded_target_contribution_contexts", 0)
        if record.get("generation"):
            gen_counts[record["generation"].get("parse_status", "missing")] += 1
        for judgment in record.get("judgments", []):
            total_judgments += 1
            parse_counts[judgment.get("parse_status", "missing")] += 1
            input_tokens += judgment.get("input_tokens") or 0
            output_tokens += judgment.get("output_tokens") or 0
        if record.get("generation"):
            input_tokens += record["generation"].get("input_tokens") or 0
            output_tokens += record["generation"].get("output_tokens") or 0
    parse_ok = parse_counts.get("ok", 0)
    gen_ok = gen_counts.get("ok", 0)
    return {
        "hits": hits,
        "hit_at_10": round(hits / max(len(records), 1) * 100, 2),
        "total_judgments": total_judgments,
        "judge_parse_ok": parse_ok,
        "judge_parse_fail": total_judgments - parse_ok,
        "judge_parse_rate": round(parse_ok / max(total_judgments, 1) * 100, 2),
        "judge_parse_status_counts": dict(parse_counts),
        "generation_parse_ok": gen_ok,
        "generation_parse_fail": sum(gen_counts.values()) - gen_ok,
        "generation_parse_status_counts": dict(gen_counts),
        "excluded_target_title_contexts": excluded_target_title,
        "excluded_target_contribution_contexts": excluded_target_contribution,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def write_output(path: Path, output: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")


def load_fixed_source(source: str, input_path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = input_path or SOURCE_DEFAULTS[source]
    obj = load_json(path)
    field = SOURCE_IDEA_FIELDS[source]
    records = []
    for record in obj.get("targets", []):
        records.append(
            {
                "target_id": record.get("target_id"),
                "ideas": record.get(field, []),
                "source_metadata": {
                    "source_file": display_path(path),
                    "idea_field": field,
                    "legacy_hit": record.get("hit"),
                    "legacy_note": "legacy labels are not used by this script",
                },
            }
        )
    return records, {"source": source, "source_file": display_path(path), "idea_field": field}


def load_direct_output(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    obj = load_json(path)
    records = []
    for record in obj.get("targets", []):
        records.append(
            {
                "target_id": record.get("target_id"),
                "ideas": record.get("generated_ideas", []),
                "source_metadata": {
                    "source_file": display_path(path),
                    "idea_field": "generated_ideas",
                    "generator_provider": obj.get("generator_provider"),
                    "generator_model": obj.get("generator_model"),
                },
            }
        )
    return records, {"source": "direct_output", "source_file": display_path(path), "idea_field": "generated_ideas"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sci-Reasoning-aligned reproduction runner")
    parser.add_argument("--mode", required=True, choices=["direct", "rejudge"])
    parser.add_argument("--protocol", default="paper_json", choices=["paper_json", "repo_binary"])
    parser.add_argument("--eval-data", default=str(DEFAULT_EVAL_DATA))
    parser.add_argument("--context-source", default="cache", choices=["cache"])
    parser.add_argument("--context-cache", default=str(DEFAULT_CONTEXT_CACHE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--provider", required=True, choices=["mimo", "sjtu"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--judge-provider", choices=["mimo", "sjtu"])
    parser.add_argument("--judge-model")
    parser.add_argument("--source", choices=sorted(SOURCE_IDEA_FIELDS))
    parser.add_argument("--input", help="Input path for --source direct_output or source override")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-chars-per-paper", type=int, default=6000)
    parser.add_argument(
        "--allow-target-title-context",
        action="store_true",
        help="Do not drop cached predecessor content containing exact target title/contribution text",
    )
    parser.add_argument(
        "--allow-target-text-context",
        action="store_true",
        help="Alias for --allow-target-title-context",
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--judge-max-tokens", type=int, default=4096)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()
    allow_target_text_context = args.allow_target_title_context or args.allow_target_text_context

    eval_records = load_eval_records(Path(args.eval_data))
    eval_by_id = {r["target_id"]: r for r in eval_records}
    context_cache = load_context_cache(Path(args.context_cache))
    targets = eval_records[: args.limit] if args.limit else eval_records

    if args.mode == "direct":
        source_meta = {
            "source": "direct_generation",
            "context_source": args.context_source,
            "context_cache": display_path(Path(args.context_cache)) if args.context_source == "cache" else None,
        }
        fixed_records = None
    else:
        if not args.source:
            print("--source is required for --mode rejudge")
            return 1
        input_path = Path(args.input) if args.input else None
        if args.source == "direct_output":
            if not input_path:
                print("--input is required for --source direct_output")
                return 1
            fixed_records, source_meta = load_direct_output(input_path)
        else:
            fixed_records, source_meta = load_fixed_source(args.source, input_path)
        by_id = {r["target_id"]: r for r in fixed_records}
        targets = [t for t in targets if t["target_id"] in by_id]

    judge_provider = args.judge_provider or args.provider
    judge_model = args.judge_model or args.model
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gen_slug = f"{args.provider}-{safe_model_slug(args.model)}"
    judge_slug = f"{judge_provider}-{safe_model_slug(judge_model)}"
    scope = f"{len(targets)}t"
    if args.output:
        output_path = Path(args.output)
    elif args.mode == "direct":
        output_path = output_dir / f"direct10_{gen_slug}_judge-{judge_slug}_{args.protocol}_ctx-{args.context_source}_{scope}_20260615.json"
    else:
        source_slug = args.source
        if args.source == "direct_output" and args.input:
            source_slug = f"direct_output_{Path(args.input).stem}"
        output_path = output_dir / f"rejudge_{source_slug}_{judge_slug}_{args.protocol}_ctx-{args.context_source}_{scope}_20260615.json"

    issues = []
    if not args.dry_run:
        if importlib.util.find_spec("openai") is None:
            issues.append("missing_python_package:openai")
    for target in targets:
        if not target.get("contribution"):
            issues.append(f"missing_contribution:{target.get('target_id')}")
        if target.get("title") not in context_cache:
            issues.append(f"missing_context_cache:{target.get('target_id')}")
        if args.mode == "rejudge":
            ideas = by_id[target["target_id"]]["ideas"]
            if len(ideas) != args.k:
                issues.append(f"idea_count_not_{args.k}:{target.get('target_id')}:{len(ideas)}")

    print(f"Mode: {args.mode}")
    print(f"Protocol: {args.protocol}")
    print(f"Targets: {len(targets)}")
    print(f"Generator: {args.provider}/{args.model}")
    print(f"Judge: {judge_provider}/{judge_model}")
    print(f"Context source: {args.context_source}")
    if args.context_source == "cache":
        print(f"Context cache: {display_path(Path(args.context_cache))}")
    print(f"Output: {display_path(output_path)}")

    if issues:
        print("INPUT INVALID:")
        for issue in issues[:100]:
            print(f"  - {issue}")
        return 1

    if args.dry_run:
        print("Dry run complete; no API calls made.")
        for target in targets[:3]:
            if args.mode == "rejudge":
                ideas = by_id[target["target_id"]]["ideas"]
                print(f"  {target['target_id']}: fixed_ideas={len(ideas)}")
                continue
            predecessor_details = context_cache[target["title"]]
            context, meta = build_context(
                predecessor_details,
                args.max_chars_per_paper,
                target["title"],
                target.get("contribution", ""),
                not allow_target_text_context,
            )
            print(f"  {target['target_id']}: context_chars={len(context)} usable_preds={meta['usable_predecessors']}")
        return 0

    results: list[dict[str, Any]] = []
    completed = set()
    if args.resume and output_path.exists():
        existing = load_json(output_path)
        seen = set()
        dropped = 0
        for record in existing.get("targets", []):
            tid = record.get("target_id")
            complete = (
                tid
                and tid not in seen
                and len(record.get("judgments", [])) == args.k
                and all(j.get("parse_status") == "ok" for j in record.get("judgments", []))
            )
            if args.mode == "direct":
                complete = complete and len(record.get("generated_ideas", [])) == args.k and record.get("generation", {}).get("parse_status") == "ok"
            if complete:
                results.append(record)
                seen.add(tid)
            else:
                dropped += 1
        completed = seen
        print(f"Resuming: {len(completed)} complete targets")
        if dropped:
            print(f"Dropped {dropped} incomplete/duplicate records")

    def checkpoint() -> None:
        metrics = recompute(results)
        output = {
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "kind": f"scireasoning_{args.mode}",
            "protocol": args.protocol,
            "protocol_sources": {
                "paper": "2601.04577v1.pdf Section 5.1 and Appendix B.4",
                "repo": "Sci-Reasoning/research_idea_evaluation/code/evaluate_idea_generation_v4_exa_improved.py",
            },
            "mode": args.mode,
            "source_metadata": source_meta,
            "context_source": args.context_source,
            "exclude_target_title_context": not allow_target_text_context,
            "exclude_target_text_context": not allow_target_text_context,
            "context_cache": display_path(Path(args.context_cache)) if args.context_source == "cache" else None,
            "max_chars_per_paper": args.max_chars_per_paper,
            "generator_provider": args.provider,
            "generator_model": args.model,
            "judge_provider": judge_provider,
            "judge_model": judge_model,
            "temperature": args.temperature,
            "judge_temperature": args.judge_temperature,
            "max_tokens": args.max_tokens,
            "judge_max_tokens": args.judge_max_tokens,
            "sleep_seconds": args.sleep_seconds,
            "k": args.k,
            "total_targets": len(targets),
            "completed": len(results),
            "all_complete": len(results) == len(targets) and metrics["total_judgments"] == len(targets) * args.k,
            **metrics,
            "targets": results,
        }
        write_output(output_path, output)

    remaining = [target for target in targets if target["target_id"] not in completed]
    for idx, target in enumerate(remaining, 1):
        print(f"\n[{idx}/{len(remaining)}] {target['target_id']}: {target['title'][:72]}...")

        if args.mode == "direct":
            predecessor_details = context_cache[target["title"]]
            context, context_meta = build_context(
                predecessor_details,
                args.max_chars_per_paper,
                target["title"],
                target.get("contribution", ""),
                not allow_target_text_context,
            )
            context_meta["context_source"] = args.context_source
            prompt = GENERATION_PROMPT.format(k=args.k, context=context)
            try:
                if not context.strip():
                    ideas = []
                    generation = {
                        "parse_status": "no_context",
                        "raw_response": "",
                        "input_tokens": None,
                        "output_tokens": None,
                        "finish_reason": None,
                    }
                else:
                    gen_result = call_chat(
                        args.provider,
                        args.model,
                        [{"role": "user", "content": prompt}],
                        args.temperature,
                        args.max_tokens,
                        args.sleep_seconds,
                    )
                    ideas = parse_numbered_ideas(gen_result.get("content") or "", args.k)
                    generation = {
                        "parse_status": "ok" if len(ideas) == args.k else "idea_count_mismatch",
                        "raw_response": gen_result.get("content") or "",
                        "input_tokens": gen_result.get("input_tokens"),
                        "output_tokens": gen_result.get("output_tokens"),
                        "finish_reason": gen_result.get("finish_reason"),
                    }
            except Exception as exc:
                ideas = []
                generation = {
                    "parse_status": "api_error",
                    "raw_response": "",
                    "error": str(exc)[:500],
                    "input_tokens": None,
                    "output_tokens": None,
                    "finish_reason": None,
                }
        else:
            fixed = by_id[target["target_id"]]
            ideas = fixed["ideas"]
            generation = None
            context_meta = {"context_source": "not_used_in_rejudge"}

        judgments = []
        for idea_idx, idea in enumerate(ideas[: args.k]):
            judgment = judge_idea(
                judge_provider,
                judge_model,
                args.protocol,
                idea,
                target["title"],
                target["contribution"],
                args.judge_temperature,
                args.judge_max_tokens,
                args.sleep_seconds,
            )
            judgment["idea_index"] = idea_idx
            judgments.append(judgment)
            if judgment.get("is_match") is True:
                print(f"  Idea {idea_idx + 1}: MATCH")
            elif judgment.get("parse_status") != "ok":
                print(f"  Idea {idea_idx + 1}: {judgment.get('parse_status')}")

        record = {
            "target_id": target["target_id"],
            "paper_title": target["title"],
            "contribution": target["contribution"],
            "context_metadata": context_meta,
            "generated_ideas": ideas if args.mode == "direct" else [],
            "final_ideas": ideas if args.mode == "rejudge" else ideas,
            "judgments": judgments,
            "timestamp": datetime.now().isoformat(),
        }
        if generation is not None:
            record["generation"] = generation
        if args.mode == "rejudge":
            record["source_metadata"] = by_id[target["target_id"]]["source_metadata"]
        results.append(record)
        checkpoint()
        print(f"  {'HIT' if any(j.get('is_match') is True for j in judgments) else 'MISS'}; checkpoint saved")

    checkpoint()
    metrics = recompute(results)
    print("\nComplete")
    print(f"Hits: {metrics['hits']}/{len(results)} ({metrics['hit_at_10']}%)")
    print(f"Judge parse: {metrics['judge_parse_ok']}/{metrics['total_judgments']} ({metrics['judge_parse_rate']}%)")
    print(f"Output: {display_path(output_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
