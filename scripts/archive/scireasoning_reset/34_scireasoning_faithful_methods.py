#!/usr/bin/env python3
"""
Generate method candidate sets under the Sci-Reasoning reset protocol.

This script is for methods after the Direct-10 reset passes. It uses the same
cached Exa-retrieved predecessor-content path as script 33 and never uses local
target-derived synthesis narratives, predecessor relationship sentences, target
titles, or target contributions during generation/selection.

It outputs selected final ideas in a Direct-output-compatible shape so that
script 33 can evaluate them with the same judge:

  python3 scripts/33_scireasoning_faithful_reproduction.py \
    --mode rejudge --source direct_output --input METHOD_OUTPUT.json ...
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAITH_SCRIPT = PROJECT_ROOT / "scripts" / "33_scireasoning_faithful_reproduction.py"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "20260615_scireasoning_faithful"


PATTERNS = [
    {
        "id": "gap_driven_reframing",
        "name": "Gap-Driven Reframing",
        "instruction": "Identify a concrete limitation, gap, or mismatched assumption in the predecessor papers, then reframe the problem so different tools or objectives become applicable.",
    },
    {
        "id": "cross_domain_synthesis",
        "name": "Cross-Domain Synthesis",
        "instruction": "Import ideas, methods, or formalisms from a different research domain to address a problem suggested by the predecessor papers.",
    },
    {
        "id": "representation_shift",
        "name": "Representation Shift",
        "instruction": "Replace a core primitive, representation, or data structure used by the predecessor papers with one that simplifies the problem or unlocks new capabilities.",
    },
    {
        "id": "data_evaluation_engineering",
        "name": "Data & Evaluation Engineering",
        "instruction": "Design a dataset, benchmark, diagnostic, or evaluation protocol that reveals a limitation in the predecessor papers and enables a new contribution.",
    },
    {
        "id": "formal_experimental_tightening",
        "name": "Formal-Experimental Tightening",
        "instruction": "Tighten an empirical claim with formal analysis, or design experiments that test and refine the mechanisms suggested by the predecessor papers.",
    },
]


BCS_PROMPT = """You are a research scientist analyzing recent papers to identify promising research directions.

Based on the following papers, generate exactly {n} diverse research ideas that could naturally follow from this body of work. Each idea should:
1. Build upon concepts, methods, or findings from these papers
2. Be specific and actionable, not vague
3. Represent a meaningful contribution to the field
4. Cover a different angle from the other ideas in this batch

Papers:
{context}

Generate exactly {n} research ideas. For each idea, provide:
- A concise title (1 line)
- A brief description of the key contribution (2-3 sentences)

Format your response as a numbered list (1-{n})."""


PGCR_PROMPT = """You are a research scientist applying a specific innovation pattern to recent papers.

Innovation pattern: {pattern_name}
Pattern instruction: {pattern_instruction}

Based on the following papers, generate exactly {n} research ideas that could naturally follow from this body of work while clearly applying the innovation pattern. Each idea should:
1. Build upon concepts, methods, or findings from these papers
2. Be specific and actionable, not vague
3. Represent a meaningful contribution to the field
4. Use the innovation pattern as a search heuristic, not as a label

Papers:
{context}

Generate exactly {n} research ideas. For each idea, provide:
- A concise title (1 line)
- A brief description of the key contribution (2-3 sentences)

Format your response as a numbered list (1-{n})."""


EVOLVE_PROMPT = """You are improving a pool of candidate scientific research ideas using lightweight mutation and crossover.

Use only the predecessor papers and seed ideas below. Do not infer or mention any hidden target paper.

Papers:
{context}

Seed ideas:
{seed_text}

Generate exactly {n} new research ideas. Use a mix of:
1. crossover: combine mechanisms from two seed ideas;
2. mutation: change one assumption, representation, data setting, or evaluation target;
3. specialization: turn a broad idea into a concrete technical contribution.

Each new idea must still be grounded in the predecessor papers and must not duplicate the seed ideas.

Format your response as a numbered list (1-{n}), with a concise title and 2-3 sentence description for each idea."""


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "while", "of", "to", "in", "for",
    "on", "with", "by", "from", "as", "at", "is", "are", "be", "this", "that",
    "these", "those", "it", "its", "their", "using", "use", "uses", "used",
    "model", "models", "method", "methods", "paper", "papers", "approach",
}


def load_faith_module():
    spec = importlib.util.spec_from_file_location("faith", FAITH_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def normalize_words(text: str) -> set[str]:
    words = set(re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text.lower()))
    return words - STOPWORDS


def idea_text(idea: dict[str, Any]) -> str:
    return " ".join(
        str(idea.get(k, ""))
        for k in ["idea_title", "idea_description", "idea_text", "method_tag", "pattern"]
    )


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def context_words(context: str) -> set[str]:
    # Use section headings and body text, but cap to avoid every generic word dominating.
    words = normalize_words(context[:60000])
    return words


def score_candidates(candidates: list[dict[str, Any]], context: str) -> list[dict[str, Any]]:
    ctx_words = context_words(context)
    seen_titles = set()
    scored = []
    for idx, cand in enumerate(candidates):
        title = cand.get("idea_title", "").strip().lower()
        words = normalize_words(idea_text(cand))
        specificity = min(len(words) / 55.0, 1.0)
        grounding = len(words & ctx_words) / max(len(words), 1)
        duplicate_penalty = 1.0 if title in seen_titles else 0.0
        seen_titles.add(title)
        score = 0.55 * specificity + 0.45 * min(grounding * 3.0, 1.0) - duplicate_penalty
        cand = dict(cand)
        cand["_selector"] = {
            "specificity": round(specificity, 4),
            "context_grounding": round(grounding, 4),
            "duplicate_penalty": duplicate_penalty,
            "score": round(score, 4),
        }
        scored.append(cand)
    scored.sort(key=lambda x: x["_selector"]["score"], reverse=True)
    return scored


def select_diverse(candidates: list[dict[str, Any]], context: str, k: int) -> list[dict[str, Any]]:
    selected = []
    selected_words = []
    for cand in score_candidates(candidates, context):
        words = normalize_words(idea_text(cand))
        if any(jaccard(words, prev) > 0.58 for prev in selected_words):
            continue
        public = {key: val for key, val in cand.items() if not key.startswith("_")}
        public["selector_diagnostics"] = cand.get("_selector", {})
        selected.append(public)
        selected_words.append(words)
        if len(selected) >= k:
            break
    if len(selected) < k:
        used = {idea.get("candidate_id") for idea in selected}
        for cand in candidates:
            if cand.get("candidate_id") in used:
                continue
            public = {key: val for key, val in cand.items() if not key.startswith("_")}
            public.setdefault("selector_diagnostics", {"fallback_fill": True})
            selected.append(public)
            if len(selected) >= k:
                break
    return selected[:k]


def make_candidates(raw_ideas: list[dict[str, str]], target_id: str, method: str, batch: str, start: int = 0, pattern: str = "") -> list[dict[str, Any]]:
    candidates = []
    for offset, idea in enumerate(raw_ideas):
        idx = start + offset
        candidates.append(
            {
                "candidate_id": f"{target_id}_{method}_{batch}_{idx:03d}",
                "idea_title": idea.get("idea_title", ""),
                "idea_description": idea.get("idea_description", ""),
                "idea_text": idea.get("idea_text", ""),
                "method_tag": method,
                "pattern": pattern,
            }
        )
    return candidates


def call_generation(faith, args, prompt: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    result = faith.call_chat(
        args.provider,
        args.model,
        [{"role": "user", "content": prompt}],
        args.temperature,
        args.max_tokens,
        args.sleep_seconds,
    )
    ideas = faith.parse_numbered_ideas(result.get("content") or "", args.expected_per_call)
    return ideas, {
        "parse_status": "ok" if len(ideas) == args.expected_per_call else "idea_count_mismatch",
        "raw_response": result.get("content") or "",
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "finish_reason": result.get("finish_reason"),
        "ideas_parsed": len(ideas),
    }


def generate_bcs(faith, args, target_id: str, context: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_candidates = []
    calls = []
    batches = math.ceil(args.num_candidates / args.expected_per_call)
    for batch_idx in range(batches):
        n = min(args.expected_per_call, args.num_candidates - len(all_candidates))
        prompt = BCS_PROMPT.format(n=n, context=context)
        old_expected = args.expected_per_call
        args.expected_per_call = n
        ideas, meta = call_generation(faith, args, prompt)
        args.expected_per_call = old_expected
        calls.append({"batch": batch_idx, **meta})
        all_candidates.extend(make_candidates(ideas, target_id, "bcs", str(batch_idx), len(all_candidates)))
    return all_candidates, calls


def generate_pgcr(faith, args, target_id: str, context: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_candidates = []
    calls = []
    for pattern in PATTERNS:
        prompt = PGCR_PROMPT.format(
            pattern_name=pattern["name"],
            pattern_instruction=pattern["instruction"],
            n=args.candidates_per_pattern,
            context=context,
        )
        old_expected = args.expected_per_call
        args.expected_per_call = args.candidates_per_pattern
        ideas, meta = call_generation(faith, args, prompt)
        args.expected_per_call = old_expected
        calls.append({"pattern_id": pattern["id"], "pattern": pattern["name"], **meta})
        all_candidates.extend(
            make_candidates(ideas, target_id, "pgcr", pattern["id"], len(all_candidates), pattern["name"])
        )
    return all_candidates, calls


def generate_se_bcs(faith, args, target_id: str, context: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed_count = min(args.seed_candidates, args.num_candidates)
    old_num = args.num_candidates
    args.num_candidates = seed_count
    seeds, calls = generate_bcs(faith, args, target_id, context)
    args.num_candidates = old_num

    seed_text = "\n".join(
        f"{i+1}. {cand.get('idea_title')}: {cand.get('idea_description')}"
        for i, cand in enumerate(select_diverse(seeds, context, min(10, len(seeds))))
    )
    remaining = max(args.num_candidates - len(seeds), 0)
    evolved = []
    evolve_batches = math.ceil(remaining / args.expected_per_call) if remaining else 0
    for batch_idx in range(evolve_batches):
        n = min(args.expected_per_call, remaining - len(evolved))
        prompt = EVOLVE_PROMPT.format(context=context, seed_text=seed_text, n=n)
        old_expected = args.expected_per_call
        args.expected_per_call = n
        ideas, meta = call_generation(faith, args, prompt)
        args.expected_per_call = old_expected
        calls.append({"batch": f"evolve_{batch_idx}", **meta})
        evolved.extend(make_candidates(ideas, target_id, "se_bcs", f"evolve_{batch_idx}", len(evolved)))
    return seeds + evolved, calls


def recompute(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_candidates = sum(len(r.get("candidate_pool", [])) for r in records)
    total_selected = sum(len(r.get("generated_ideas", [])) for r in records)
    parse_counts = Counter()
    input_tokens = 0
    output_tokens = 0
    excluded = 0
    excluded_contribution = 0
    for record in records:
        excluded += record.get("context_metadata", {}).get("excluded_target_title_contexts", 0)
        excluded_contribution += record.get("context_metadata", {}).get("excluded_target_contribution_contexts", 0)
        for call in record.get("generation_calls", []):
            parse_counts[call.get("parse_status", "missing")] += 1
            input_tokens += call.get("input_tokens") or 0
            output_tokens += call.get("output_tokens") or 0
    return {
        "completed": len(records),
        "total_candidates": total_candidates,
        "total_selected": total_selected,
        "generation_parse_status_counts": dict(parse_counts),
        "generation_parse_ok": parse_counts.get("ok", 0),
        "generation_parse_fail": sum(parse_counts.values()) - parse_counts.get("ok", 0),
        "excluded_target_title_contexts": excluded,
        "excluded_target_contribution_contexts": excluded_contribution,
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def main() -> int:
    faith = load_faith_module()
    parser = argparse.ArgumentParser(description="Generate Sci-Reasoning reset-method final idea sets")
    parser.add_argument("--method", required=True, choices=["bcs", "pgcr", "se_bcs"])
    parser.add_argument("--provider", required=True, choices=["mimo", "sjtu"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--eval-data", default=str(faith.DEFAULT_EVAL_DATA))
    parser.add_argument("--context-source", default="cache", choices=["cache"])
    parser.add_argument("--context-cache", default=str(faith.DEFAULT_CONTEXT_CACHE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--num-candidates", type=int, default=50)
    parser.add_argument("--seed-candidates", type=int, default=25)
    parser.add_argument("--candidates-per-pattern", type=int, default=10)
    parser.add_argument("--expected-per-call", type=int, default=10)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-chars-per-paper", type=int, default=6000)
    parser.add_argument(
        "--allow-target-title-context",
        action="store_true",
        help="Do not drop cached predecessor content containing exact target title/contribution text",
    )
    parser.add_argument("--allow-target-text-context", action="store_true", help="Alias for --allow-target-title-context")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()
    allow_target_text_context = args.allow_target_title_context or args.allow_target_text_context

    eval_records = faith.load_eval_records(Path(args.eval_data))
    context_cache = faith.load_context_cache(Path(args.context_cache))
    targets = eval_records[: args.limit] if args.limit else eval_records
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_slug = f"{args.provider}-{faith.safe_model_slug(args.model)}"
    scope = f"{len(targets)}t"
    output_path = (
        Path(args.output)
        if args.output
        else output_dir / f"method_{args.method}_{model_slug}_{args.num_candidates}cand_ctx-{args.context_source}_{scope}_20260615.json"
    )

    issues = []
    if not args.dry_run and faith.importlib.util.find_spec("openai") is None:
        issues.append("missing_python_package:openai")
    for target in targets:
        if target.get("title") not in context_cache:
            issues.append(f"missing_context_cache:{target.get('target_id')}")
    print(f"Method: {args.method}")
    print(f"Targets: {len(targets)}")
    print(f"Model: {args.provider}/{args.model}")
    print(f"Context source: {args.context_source}")
    print(f"Output: {faith.display_path(output_path)}")
    if issues:
        print("INPUT INVALID:")
        for issue in issues[:100]:
            print(f"  - {issue}")
        return 1

    if args.dry_run:
        print("Dry run complete; no API calls made.")
        for target in targets[:3]:
            predecessor_details = context_cache[target["title"]]
            context, meta = faith.build_context(
                predecessor_details,
                args.max_chars_per_paper,
                target["title"],
                target.get("contribution", ""),
                not allow_target_text_context,
            )
            print(f"  {target['target_id']}: context_chars={len(context)} usable_preds={meta['usable_predecessors']}")
        return 0

    results = []
    completed = set()
    if args.resume and output_path.exists():
        existing = faith.load_json(output_path)
        seen = set()
        dropped = 0
        for record in existing.get("targets", []):
            complete = (
                record.get("target_id")
                and record.get("target_id") not in seen
                and len(record.get("generated_ideas", [])) == args.k
                and all(call.get("parse_status") == "ok" for call in record.get("generation_calls", []))
            )
            if complete:
                results.append(record)
                seen.add(record["target_id"])
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
            "kind": "scireasoning_method_candidates",
            "method": args.method,
            "context_source": args.context_source,
            "context_cache": faith.display_path(Path(args.context_cache)) if args.context_source == "cache" else None,
            "max_chars_per_paper": args.max_chars_per_paper,
            "exclude_target_title_context": not allow_target_text_context,
            "exclude_target_text_context": not allow_target_text_context,
            "generator_provider": args.provider,
            "generator_model": args.model,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "sleep_seconds": args.sleep_seconds,
            "k": args.k,
            "num_candidates": args.num_candidates,
            "selection": "target_hidden_greedy_diverse_lexical",
            "total_targets": len(targets),
            "all_complete": len(results) == len(targets) and metrics["total_selected"] == len(targets) * args.k,
            **metrics,
            "targets": results,
        }
        faith.write_output(output_path, output)

    generators = {
        "bcs": generate_bcs,
        "pgcr": generate_pgcr,
        "se_bcs": generate_se_bcs,
    }
    remaining = [target for target in targets if target["target_id"] not in completed]
    for idx, target in enumerate(remaining, 1):
        print(f"\n[{idx}/{len(remaining)}] {target['target_id']}: {target['title'][:72]}...")
        predecessor_details = context_cache[target["title"]]
        context, context_meta = faith.build_context(
            predecessor_details,
            args.max_chars_per_paper,
            target["title"],
            target.get("contribution", ""),
            not allow_target_text_context,
        )
        context_meta["context_source"] = args.context_source
        if not context.strip():
            candidates = []
            calls = [{"parse_status": "no_context", "ideas_parsed": 0}]
        else:
            candidates, calls = generators[args.method](faith, args, target["target_id"], context)
        selected = select_diverse(candidates, context, args.k)
        record = {
            "target_id": target["target_id"],
            "paper_title": target["title"],
            "context_metadata": context_meta,
            "candidate_pool": candidates,
            "generated_ideas": selected,
            "generation_calls": calls,
            "timestamp": datetime.now().isoformat(),
        }
        results.append(record)
        checkpoint()
        print(f"  candidates={len(candidates)} selected={len(selected)}; checkpoint saved")

    checkpoint()
    metrics = recompute(results)
    print("\nComplete")
    print(f"Completed: {metrics['completed']}/{len(targets)}")
    print(f"Candidates: {metrics['total_candidates']} Selected: {metrics['total_selected']}")
    print(f"Generation parse: {metrics['generation_parse_status_counts']}")
    print(f"Output: {faith.display_path(output_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
