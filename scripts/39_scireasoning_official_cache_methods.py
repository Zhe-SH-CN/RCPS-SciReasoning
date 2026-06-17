#!/usr/bin/env python3
"""
Target-hidden candidate-search methods for the Script38 fixed cached-context route.

This script changes only candidate generation and selection. Final evaluation uses
the official v4 binary MATCH/NO_MATCH judge and target-level Hit@10 semantics by
calling functions from scripts/38_scireasoning_official_cache_exa.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT38_PATH = PROJECT_ROOT / "scripts" / "38_scireasoning_official_cache_exa.py"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "experiments" / "20260616_script38_methods"


PATTERNS = [
    (
        "gap_reframing",
        "Identify a concrete limitation or mismatched assumption in the predecessor papers, then reframe the problem so a different objective or method becomes applicable.",
    ),
    (
        "representation_shift",
        "Replace a core representation, data structure, or modeling primitive used in the predecessor papers with one that enables a new capability.",
    ),
    (
        "data_eval",
        "Design a dataset, diagnostic, or evaluation protocol that exposes a limitation in the predecessor papers and supports a new contribution.",
    ),
    (
        "cross_domain",
        "Transfer a mechanism, formalism, or experimental design from another area into the problem family suggested by the predecessor papers.",
    ),
    (
        "mechanistic_tightening",
        "Turn an empirical observation from the predecessor papers into a sharper mechanistic, theoretical, or causal research question.",
    ),
]


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those", "into",
    "using", "use", "uses", "used", "paper", "papers", "method", "methods", "model",
    "models", "research", "idea", "ideas", "approach", "approaches", "based", "via",
}


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


PATTERN_PROMPT = """You are a research scientist applying one target-hidden search heuristic to recent papers.

Search heuristic:
{pattern_instruction}

Based on the following papers, generate exactly {n} research ideas that could naturally follow from this body of work while applying the heuristic. Each idea should:
1. Build upon concepts, methods, or findings from these papers
2. Be specific and actionable, not vague
3. Represent a meaningful contribution to the field
4. Use the heuristic as a way to search, not as a label in the idea

Papers:
{context}

Generate exactly {n} research ideas. For each idea, provide:
- A concise title (1 line)
- A brief description of the key contribution (2-3 sentences)

Format your response as a numbered list (1-{n})."""


EVOLVE_PROMPT = """You are improving candidate scientific research ideas using lightweight mutation and crossover.

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

Format your response as a numbered list (1-{n})."""


def load_script38():
    spec = importlib.util.spec_from_file_location("script38", SCRIPT38_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def configure_official(mod, args):
    mod.EXA_API_KEY = args.exa_api_key if args.exa_api_key is not None else os.getenv("EXA_API_KEY", "")
    mod.OPENAI_API_KEY = args.api_key if args.api_key is not None else os.getenv("OPENAI_API_KEY", "")
    mod.OPENAI_BASE_URL = args.base_url if args.base_url is not None else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    mod.OPENAI_MODEL = args.model if args.model is not None else os.getenv("OPENAI_MODEL", "")
    mod.MODEL_SLEEP_SECONDS = args.sleep_seconds
    if hasattr(mod, "REQUEST_TIMEOUT_SECONDS"):
        mod.REQUEST_TIMEOUT_SECONDS = args.request_timeout
    mod.CONTEXT_CACHE_PATH = Path(args.context_cache)
    mod.CONTEXT_CACHE_BY_TITLE, mod.CONTEXT_CACHE_SUMMARY = mod.load_context_cache(mod.CONTEXT_CACHE_PATH)


def build_official_context(predecessor_contents):
    context_parts = []
    for i, pred in enumerate(predecessor_contents):
        if pred.get("success") and pred.get("content"):
            content = pred["content"]
            if len(content) < 300:
                continue
            context_parts.append(
                f"=== Paper {i+1}: {pred.get('title', 'Unknown')} ===\n{content[:6000]}\n"
            )
    return "\n".join(context_parts)


def words(text: str) -> set[str]:
    found = set(re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text.lower()))
    return found - STOPWORDS


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def candidate_text(candidate: dict[str, Any]) -> str:
    return str(candidate.get("idea_text", ""))


def score_candidates(candidates: list[dict[str, Any]], context: str) -> list[dict[str, Any]]:
    context_words = words(context[:60000])
    seen = set()
    scored = []
    for cand in candidates:
        text_words = words(candidate_text(cand))
        title = candidate_text(cand).splitlines()[0].strip().lower() if candidate_text(cand) else ""
        specificity = min(len(text_words) / 55.0, 1.0)
        grounding = len(text_words & context_words) / max(len(text_words), 1)
        duplicate_penalty = 1.0 if title in seen else 0.0
        seen.add(title)
        score = 0.55 * specificity + 0.45 * min(grounding * 3.0, 1.0) - duplicate_penalty
        row = dict(cand)
        row["selector_diagnostics"] = {
            "specificity": round(specificity, 4),
            "context_grounding": round(grounding, 4),
            "duplicate_penalty": duplicate_penalty,
            "score": round(score, 4),
        }
        scored.append(row)
    scored.sort(key=lambda x: x["selector_diagnostics"]["score"], reverse=True)
    return scored


def select_diverse(candidates: list[dict[str, Any]], context: str, k: int) -> list[dict[str, Any]]:
    selected = []
    selected_words = []
    used = set()
    for cand in score_candidates(candidates, context):
        cid = cand.get("candidate_id")
        if cid in used:
            continue
        w = words(candidate_text(cand))
        if any(jaccard(w, prev) > 0.58 for prev in selected_words):
            continue
        selected.append(cand)
        selected_words.append(w)
        used.add(cid)
        if len(selected) >= k:
            break
    if len(selected) < k:
        for cand in candidates:
            cid = cand.get("candidate_id")
            if cid in used:
                continue
            fallback = dict(cand)
            fallback.setdefault("selector_diagnostics", {"fallback_fill": True})
            selected.append(fallback)
            used.add(cid)
            if len(selected) >= k:
                break
    return selected[:k]


def call_generation(mod, prompt: str, expected: int) -> tuple[list[str], dict[str, Any]]:
    result = mod.call_openai_api([{"role": "user", "content": prompt}])
    ideas = mod.parse_ideas_from_response(result["content"])
    if expected < 10:
        ideas = ideas[:expected]
    return ideas, {
        "expected": expected,
        "parsed": len(ideas),
        "parse_status": "ok" if len(ideas) == expected else "idea_count_mismatch",
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "raw_response": result["content"],
    }


def make_candidates(ideas: list[str], target_idx: int, method: str, batch: str, start: int = 0) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": f"t{target_idx:03d}_{method}_{batch}_{start+i:03d}",
            "idea_text": idea,
            "source": method,
            "batch": batch,
        }
        for i, idea in enumerate(ideas)
    ]


def generate_bcs(mod, context: str, target_idx: int, args) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = []
    calls = []
    batches = math.ceil(args.num_candidates / args.batch_size)
    for batch_idx in range(batches):
        n = min(args.batch_size, args.num_candidates - len(candidates))
        ideas, meta = call_generation(mod, BCS_PROMPT.format(n=n, context=context), n)
        calls.append({"kind": "bcs", "batch": batch_idx, **meta})
        candidates.extend(make_candidates(ideas, target_idx, "bcs", str(batch_idx), len(candidates)))
    return candidates, calls


def generate_pgcr(mod, context: str, target_idx: int, args) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = []
    calls = []
    for pattern_id, instruction in PATTERNS:
        ideas, meta = call_generation(
            mod,
            PATTERN_PROMPT.format(pattern_instruction=instruction, n=args.candidates_per_pattern, context=context),
            args.candidates_per_pattern,
        )
        calls.append({"kind": "pgcr", "pattern": pattern_id, **meta})
        candidates.extend(make_candidates(ideas, target_idx, "pgcr", pattern_id, len(candidates)))
    return candidates, calls


def generate_se_bcs(mod, context: str, target_idx: int, args) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old_num = args.num_candidates
    args.num_candidates = min(args.seed_candidates, old_num)
    seeds, calls = generate_bcs(mod, context, target_idx, args)
    args.num_candidates = old_num
    seed_text = "\n".join(
        f"{i+1}. {candidate_text(c)}"
        for i, c in enumerate(select_diverse(seeds, context, min(10, len(seeds))))
    )
    evolved = []
    remaining = max(old_num - len(seeds), 0)
    batches = math.ceil(remaining / args.batch_size) if remaining else 0
    for batch_idx in range(batches):
        n = min(args.batch_size, remaining - len(evolved))
        ideas, meta = call_generation(mod, EVOLVE_PROMPT.format(context=context, seed_text=seed_text, n=n), n)
        calls.append({"kind": "se_bcs_evolve", "batch": batch_idx, **meta})
        evolved.extend(make_candidates(ideas, target_idx, "se_bcs", f"evolve_{batch_idx}", len(evolved)))
    return seeds + evolved, calls


def generate_rcps(mod, predecessor_contents, context: str, target_idx: int, args):
    calls = []
    direct_text, in_tok, out_tok = mod.generate_research_ideas(predecessor_contents, k=10)
    direct_ideas = mod.parse_ideas_from_response(direct_text or "")
    calls.append({
        "kind": "direct_anchor",
        "expected": 10,
        "parsed": len(direct_ideas),
        "parse_status": "ok" if len(direct_ideas) == 10 else "idea_count_mismatch",
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "raw_response": direct_text or "",
    })
    direct_candidates = make_candidates(direct_ideas, target_idx, "direct_anchor", "0", 0)
    bcs_candidates, bcs_calls = generate_bcs(mod, context, target_idx, args)
    calls.extend(bcs_calls)
    anchors = direct_candidates[: min(args.anchor_slots, len(direct_candidates))]
    fill = select_diverse(bcs_candidates, context, max(args.k - len(anchors), 0))
    selected = anchors + fill
    return direct_candidates + bcs_candidates, calls, selected[: args.k]


def evaluate_selected(mod, selected: list[dict[str, Any]], paper_data: dict[str, Any]) -> tuple[bool, int | None, list[dict[str, Any]], int, int]:
    hit = False
    matching_idx = None
    judgments = []
    input_tokens = 0
    output_tokens = 0
    for idx, cand in enumerate(selected):
        idea = candidate_text(cand)
        is_match, in_tok, out_tok = mod.judge_similarity(
            idea,
            paper_data["paper_title"],
            paper_data["contribution"],
        )
        input_tokens += in_tok
        output_tokens += out_tok
        judgments.append({"idea_idx": idx, "idea_text": idea[:200], "is_match": is_match})
        if is_match and not hit:
            hit = True
            matching_idx = idx
        time.sleep(0.2)
    return hit, matching_idx, judgments, input_tokens, output_tokens


def output_paths(path: Path) -> tuple[Path, Path]:
    return path, path.with_name(f"{path.stem}_interim{path.suffix}")


def save_output(path: Path, results: list[dict[str, Any]], args, mod, start_time: float, interim: bool):
    final_path, interim_path = output_paths(path)
    out_path = interim_path if interim else final_path
    hits = sum(1 for r in results if r["hit_at_k"])
    generation_calls = [c for r in results for c in r.get("generation_calls", [])]
    parse_counts = Counter(c.get("parse_status", "missing") for c in generation_calls)
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)
    alignments = [r.get("cache_alignment", {}) for r in results]
    output = {
        "summary": {
            "model": mod.OPENAI_MODEL,
            "method": args.method,
            "k": args.k,
            "num_candidates": args.num_candidates,
            "anchor_slots": args.anchor_slots if args.method == "rcps" else None,
            "evaluation_protocol": "official_v4_binary_judge_hit_at_k",
            "official_runner": str(SCRIPT38_PATH),
            "official_parser_function": "parse_ideas_from_response",
            "official_judge_function": "judge_similarity",
            "method_scope": "candidate_generation_and_target_hidden_selection_only",
            "crawl_method": "cached_exa_from_scireasoning_result",
            "cache_source": str(mod.CONTEXT_CACHE_PATH),
            "cache_source_summary": mod.CONTEXT_CACHE_SUMMARY,
            "cache_mode": "target_title_to_predecessor_details",
            "cache_caveat": (
                "Cached predecessor_details are loaded by target title from a Sci-Reasoning result artifact. "
                "They are Exa-retrieved paper contents but may not match the current synthesis predecessor-title list."
            ),
            "total_papers": len(results),
            "hits": hits,
            "hit_rate_percent": round(hits / len(results) * 100, 2) if results else 0,
            "generation_parse_status_counts": dict(parse_counts),
            "average_cached_predecessors": round(
                sum(a.get("cached_predecessor_count", 0) for a in alignments) / len(alignments), 2
            ) if alignments else 0,
            "minimum_synthesis_cache_title_overlap": min(
                (a.get("normalized_title_overlap_count", 0) for a in alignments),
                default=0,
            ),
            "runtime_minutes": round((time.time() - start_time) / 60, 2),
            "cost": {
                "input_tokens": total_input,
                "output_tokens": total_output,
            },
            "timestamp": datetime.now().isoformat(),
        },
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"    Results saved to: {out_path}")


def load_resume(path: Path) -> list[dict[str, Any]]:
    final_path, interim_path = output_paths(path)
    resume_path = final_path if final_path.exists() else interim_path if interim_path.exists() else None
    if resume_path is None:
        return []
    with open(resume_path, "r") as f:
        data = json.load(f)
    records = []
    seen = set()
    for record in data.get("results", []):
        title = record.get("paper_title")
        complete = (
            title
            and title not in seen
            and len(record.get("generated_ideas", [])) == len(record.get("judgments", []))
            and "hit_at_k" in record
        )
        if complete:
            records.append(record)
            seen.add(title)
    print(f"Resuming from {resume_path}: {len(records)} completed targets")
    return records


def main() -> int:
    mod = load_script38()
    parser = argparse.ArgumentParser(description="Script38 fixed cached-context candidate-search methods")
    parser.add_argument("--method", required=True, choices=["bcs", "pgcr", "se_bcs", "rcps"])
    parser.add_argument("--data-dir", default=str(mod.DEFAULT_DATA_DIR))
    parser.add_argument("--context-cache", default=str(mod.DEFAULT_CONTEXT_CACHE))
    parser.add_argument("--output")
    parser.add_argument("--smoke", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", dest="base_url", default=None)
    parser.add_argument("--api-key", dest="api_key", default=None)
    parser.add_argument("--exa-api-key", dest="exa_api_key", default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--request-timeout", type=float, default=240.0)
    parser.add_argument("--num-candidates", type=int, default=30)
    parser.add_argument("--seed-candidates", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--candidates-per-pattern", type=int, default=6)
    parser.add_argument("--anchor-slots", type=int, default=6)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    configure_official(mod, args)
    papers = mod.load_synthesis_data(args.data_dir)
    if args.smoke:
        papers = papers[: args.smoke]
    output_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR / f"{args.method}_{mod.OPENAI_MODEL}_cache_exa_{len(papers)}t.json"
    )

    print("=" * 70)
    print("Script38 Fixed Cached-Context Method Evaluation")
    print("=" * 70)
    print(f"Model: {mod.OPENAI_MODEL}")
    print(f"Method: {args.method}")
    print(f"Targets: {len(papers)}")
    print(f"Output: {output_path}")

    missing = []
    if not args.dry_run and not mod.OPENAI_API_KEY:
        missing.append("missing_env:OPENAI_API_KEY")
    if not mod.OPENAI_MODEL:
        missing.append("missing_env:OPENAI_MODEL")
    for paper in papers:
        if paper["paper_title"] not in mod.CONTEXT_CACHE_BY_TITLE:
            missing.append(f"missing_cache:{paper['paper_title'][:80]}")
    if missing:
        print("INPUT INVALID:")
        for item in missing[:100]:
            print(f"  - {item}")
        return 1

    if args.dry_run:
        print("Dry run: no model API calls will be made.")
        for idx, paper in enumerate(papers[:3]):
            cached = mod.CONTEXT_CACHE_BY_TITLE.get(paper["paper_title"], [])
            alignment = mod.cache_alignment(paper["predecessors"], cached)
            print(
                f"  [{idx}] {paper['paper_title'][:80]} | cached={len(cached)} | "
                f"overlap={alignment['normalized_title_overlap_count']}"
            )
        return 0

    results = load_resume(output_path) if args.resume else []
    completed = {r["paper_title"] for r in results}
    start_time = time.time()

    for idx, paper in enumerate(papers):
        if paper["paper_title"] in completed:
            continue
        print(f"\n{'='*70}")
        print(f"[{idx}] {paper['paper_title'][:70]}...")
        predecessor_contents = mod.CONTEXT_CACHE_BY_TITLE.get(paper["paper_title"], [])
        alignment = mod.cache_alignment(paper["predecessors"], predecessor_contents)
        context = build_official_context(predecessor_contents)
        if not context:
            candidates, calls, selected = [], [{"parse_status": "no_context"}], []
            gen_in = gen_out = 0
        elif args.method == "bcs":
            candidates, calls = generate_bcs(mod, context, idx, args)
            selected = select_diverse(candidates, context, args.k)
        elif args.method == "pgcr":
            candidates, calls = generate_pgcr(mod, context, idx, args)
            selected = select_diverse(candidates, context, args.k)
        elif args.method == "se_bcs":
            candidates, calls = generate_se_bcs(mod, context, idx, args)
            selected = select_diverse(candidates, context, args.k)
        else:
            candidates, calls, selected = generate_rcps(mod, predecessor_contents, context, idx, args)

        gen_in = sum(c.get("input_tokens", 0) for c in calls)
        gen_out = sum(c.get("output_tokens", 0) for c in calls)
        hit, matching_idx, judgments, judge_in, judge_out = evaluate_selected(mod, selected, paper)
        crawl_successes = sum(1 for p in predecessor_contents if p.get("success"))
        quality_content = sum(
            1 for p in predecessor_contents if p.get("content_quality") in ["good", "good_from_html"]
        )
        crawl_rate = crawl_successes / len(predecessor_contents) if predecessor_contents else 0.0
        quality_rate = quality_content / len(predecessor_contents) if predecessor_contents else 0.0
        result = {
            "paper_idx": idx,
            "paper_title": paper["paper_title"],
            "contribution": paper["contribution"],
            "num_predecessors": len(paper["predecessors"]),
            "predecessors_crawled": crawl_successes,
            "quality_content": quality_content,
            "crawl_rate": crawl_rate,
            "quality_rate": quality_rate,
            "ideas_generated": len(selected),
            "hit_at_k": hit,
            "matching_idea_idx": matching_idx,
            "input_tokens": gen_in + judge_in,
            "output_tokens": gen_out + judge_out,
            "predecessor_details": predecessor_contents,
            "cache_alignment": alignment,
            "candidate_pool": candidates,
            "generation_calls": calls,
            "generated_ideas": [candidate_text(c) for c in selected],
            "judgments": judgments,
        }
        results.append(result)
        completed.add(paper["paper_title"])
        hits = sum(1 for r in results if r["hit_at_k"])
        print(f"    selected={len(selected)} candidates={len(candidates)} hit={hit}")
        print(f"    Progress: {len(results)}/{len(papers)} | Hits: {hits}/{len(results)} ({hits/len(results)*100:.1f}%)")
        save_output(output_path, results, args, mod, start_time, interim=True)

    save_output(output_path, results, args, mod, start_time, interim=False)
    hits = sum(1 for r in results if r["hit_at_k"])
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Papers evaluated: {len(results)}")
    print(f"Hit@10: {hits}/{len(results)} = {hits/len(results)*100:.2f}%" if results else "Hit@10: NA")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
