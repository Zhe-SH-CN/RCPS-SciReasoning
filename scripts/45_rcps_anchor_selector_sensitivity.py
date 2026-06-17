#!/usr/bin/env python3
"""
RCPS anchor-budget sensitivity and selector/component ablation.

Reuses existing RCPS candidate_pool data. Performs target-hidden reselection
and final official-v4-style binary judging. No new idea generation, no Exa calls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT38 = PROJECT_ROOT / "scripts" / "38_scireasoning_official_cache_exa.py"
SCRIPT39 = PROJECT_ROOT / "scripts" / "39_scireasoning_official_cache_methods.py"

RESULT_DIR = PROJECT_ROOT / "results" / "experiments" / "20260617_rcps_anchor_selector"
LOG_DIR = PROJECT_ROOT / "logs" / "20260617_rcps_anchor_selector"

RCPS_MODELS = {
    "gemini-3.1-pro-low": {
        "rcps": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_methods_full77" / "rcps_gemini_low_77t.json",
        "direct": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_mimo_gemini_full77" / "gemini_cache_exa_77t.json",
    },
    "gemini-pro-agent": {
        "rcps": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_methods_full77" / "rcps_gemini_pro_agent_77t.json",
        "direct": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_mimo_gemini_full77" / "gemini_pro_agent_cache_exa_77t.json",
    },
    "gemini-3-flash-agent": {
        "rcps": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_methods_full77" / "rcps_gemini_3_flash_agent_77t.json",
        "direct": PROJECT_ROOT / "results" / "experiments" / "20260616_script38_gemini_baselines" / "gemini_3_flash_agent_cache_exa_77t.json",
    },
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those", "into",
    "using", "use", "uses", "used", "paper", "papers", "method", "methods", "model",
    "models", "research", "idea", "ideas", "approach", "approaches", "based", "via",
}

ANCHOR_BUDGETS = [0, 2, 4, 6, 8, 10]


# ---- Lazy imports from scripts 38/39 ----

_s38 = None
_s39 = None


def _load_s38():
    global _s38
    if _s38 is None:
        spec = importlib.util.spec_from_file_location("s38", SCRIPT38)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _s38 = mod
    return _s38


def _load_s39():
    global _s39
    if _s39 is None:
        spec = importlib.util.spec_from_file_location("s39", SCRIPT39)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _s39 = mod
    return _s39


# ---- Helpers ----


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def words(text: str) -> set[str]:
    s39 = _load_s39()
    return s39.words(text)


def candidate_text(candidate) -> str:
    if isinstance(candidate, str):
        return candidate
    return str(candidate.get("idea_text", ""))


def build_context_for_target(target_id: str, eval_data: dict, context_cache: dict, rcps_target: dict = None) -> str:
    """Build context from predecessor_details stored in the RCPS target record."""
    s39 = _load_s39()
    # Use predecessor_details from the RCPS target if available
    if rcps_target and rcps_target.get("predecessor_details"):
        return s39.build_official_context(rcps_target["predecessor_details"])
    # Fallback: use context cache by title
    rec = eval_data.get(target_id, {})
    title = rec.get("title", "")
    details = context_cache.get(title, [])
    if details:
        return s39.build_official_context(details)
    return ""


def select_diverse(candidates: list[dict], context: str, k: int) -> list[dict]:
    s39 = _load_s39()
    return s39.select_diverse(candidates, context, k)


def select_top_score(candidates: list[dict], context: str, k: int) -> list[dict]:
    s39 = _load_s39()
    scored = s39.score_candidates(candidates, context)
    return scored[:k]


def select_by_specificity(candidates: list[dict], context: str, k: int) -> list[dict]:
    s39 = _load_s39()
    scored = s39.score_candidates(candidates, context)
    scored.sort(key=lambda x: x.get("selector_diagnostics", {}).get("specificity", 0), reverse=True)
    return scored[:k]


def select_by_grounding(candidates: list[dict], context: str, k: int) -> list[dict]:
    s39 = _load_s39()
    scored = s39.score_candidates(candidates, context)
    scored.sort(key=lambda x: x.get("selector_diagnostics", {}).get("context_grounding", 0), reverse=True)
    return scored[:k]


def select_random(candidates: list[dict], k: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    pool = list(candidates)
    rng.shuffle(pool)
    return pool[:k]


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_dotenv():
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_eval_data() -> dict:
    path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
    rows = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                rows[rec["target_id"]] = rec
    return rows


def load_context_cache() -> dict:
    s38 = _load_s38()
    cache, _ = s38.load_context_cache(s38.DEFAULT_CONTEXT_CACHE)
    return cache


def configure_judge(model_name: str, request_timeout: float, sleep_seconds: float) -> None:
    """Configure script38's OpenAI-compatible judge globals for one model row."""
    s38 = _load_s38()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    if not api_key:
        raise RuntimeError("missing Gemini/OpenAI-compatible API key in environment")
    if not base_url:
        raise RuntimeError("missing Gemini/OpenAI-compatible base URL in environment")
    s38.OPENAI_API_KEY = api_key
    s38.OPENAI_BASE_URL = base_url
    s38.OPENAI_MODEL = model_name
    s38.REQUEST_TIMEOUT_SECONDS = request_timeout
    s38.MODEL_SLEEP_SECONDS = sleep_seconds


def judge_target_fields(target: dict) -> tuple[str, str]:
    """Return target-visible fields for final judging only."""
    title = str(target.get("paper_title") or target.get("title") or "").strip()
    contribution = str(target.get("contribution") or "").strip()
    if not title or not contribution:
        raise RuntimeError(
            f"missing final-judge target fields for paper_idx={target.get('paper_idx')}"
        )
    return title, contribution


def get_targets(data: dict) -> list[dict]:
    """Get target list from JSON, handling both 'targets' and 'results' keys."""
    return data.get("targets", data.get("results", []))


def get_target_id(t: dict) -> str:
    """Get target identifier from a target record."""
    return t.get("target_id", t.get("paper_idx", ""))


def is_hit(t: dict) -> bool:
    """Check if target is a hit, handling both 'hit' and 'hit_at_k' keys."""
    return bool(t.get("hit", t.get("hit_at_k", False)))


def split_candidate_pool(target: dict) -> tuple[list[dict], list[dict]]:
    pool = target.get("candidate_pool", [])
    direct = [c for c in pool if c.get("source") == "direct_anchor"]
    bcs = [c for c in pool if c.get("source") == "bcs"]
    return direct, bcs


def build_portfolio(direct: list[dict], bcs: list[dict], context: str,
                    anchor_slots: int, selector: str, seed: int = 0) -> list[dict]:
    anchors = direct[:anchor_slots]
    fill_k = 10 - len(anchors)
    if fill_k <= 0:
        return anchors[:10]

    if selector in ("rcps_full", "default"):
        fill = select_diverse(bcs, context, fill_k)
    elif selector == "no_anchor_fill10":
        return select_diverse(bcs, context, 10)
    elif selector == "anchor6_topscore_no_diversity":
        fill = select_top_score(bcs, context, fill_k)
    elif selector == "anchor6_specificity_only":
        fill = select_by_specificity(bcs, context, fill_k)
    elif selector == "anchor6_grounding_only":
        fill = select_by_grounding(bcs, context, fill_k)
    elif selector.startswith("anchor6_random_fill_seed"):
        fill = select_random(bcs, fill_k, seed)
    elif selector == "direct_prefix10_from_rcps_call":
        return direct[:10]
    else:
        fill = select_diverse(bcs, context, fill_k)

    return anchors + fill


def verify_reconstruction(rcps_data: dict, eval_data: dict, context_cache: dict) -> list[str]:
    mismatches = []
    for target in get_targets(rcps_data):
        tid = get_target_id(target)
        stored = target.get("generated_ideas", [])
        if not stored:
            continue
        direct, bcs = split_candidate_pool(target)
        if not direct and not bcs:
            continue
        context = build_context_for_target(tid, eval_data, context_cache, target)
        reconstructed = build_portfolio(direct, bcs, context, 6, "rcps_full")
        if len(reconstructed) != len(stored):
            mismatches.append(f"{tid}: len mismatch {len(reconstructed)} vs {len(stored)}")
            continue
        for i, (r, s) in enumerate(zip(reconstructed, stored)):
            rt = candidate_text(r).strip()
            st = candidate_text(s).strip()
            if rt != st:
                mismatches.append(f"{tid}: idea {i} mismatch")
                break
    return mismatches


def judge_idea_with_s38(idea_text: str, title: str, contribution: str) -> dict:
    """Call script 38's judge_similarity with env vars set for current provider."""
    s38 = _load_s38()
    attempt = 0
    while True:
        try:
            is_match, in_tok, out_tok = s38.judge_similarity(idea_text, title, contribution)
            return {"is_match": is_match, "input_tokens": in_tok, "output_tokens": out_tok, "parse_status": "ok"}
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["429", "rate", "timeout", "connection", "reset", "502", "503"]):
                attempt += 1
                safe = s38.sanitize_api_error_text(str(e))[:200] if hasattr(s38, "sanitize_api_error_text") else str(e)[:200]
                print(f"Transient judge error attempt={attempt}; sleeping 10s; error={safe}", flush=True)
                time.sleep(10)
                continue
            safe = s38.sanitize_api_error_text(str(e))[:200] if hasattr(s38, "sanitize_api_error_text") else str(e)[:200]
            raise RuntimeError(f"non-transient judge error: {safe}") from e


def evaluate_portfolio(
    model_name: str,
    paper_idx: int,
    portfolio: list,
    title: str,
    contribution: str,
    get_cached_judgment,
    store_judgment,
    sleep_seconds: float,
) -> tuple[bool, bool, bool, int, int]:
    """Judge a fixed portfolio and return target/anchor/fill hit flags plus token counts."""
    target_hit = False
    anchor_hit = False
    fill_hit = False
    input_tokens = 0
    output_tokens = 0
    for idea in portfolio:
        idea_text = candidate_text(idea)
        cached = get_cached_judgment(model_name, paper_idx, idea_text)
        if cached:
            j = cached["judgment"]
        else:
            j = judge_idea_with_s38(idea_text, title, contribution)
            store_judgment(model_name, paper_idx, idea_text, j)
        input_tokens += int(j.get("input_tokens", 0) or 0)
        output_tokens += int(j.get("output_tokens", 0) or 0)
        if j.get("is_match"):
            target_hit = True
            if isinstance(idea, dict) and idea.get("source") == "direct_anchor":
                anchor_hit = True
            else:
                fill_hit = True
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return target_hit, anchor_hit, fill_hit, input_tokens, output_tokens


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", type=int, default=0)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--request-timeout", type=float, default=240.0)
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    load_dotenv()
    eval_data = load_eval_data()
    context_cache = load_context_cache()

    print(f"Loaded {len(eval_data)} eval records, {len(context_cache)} cache records")

    # Load all RCPS and Direct files
    model_data = {}
    for model_name, cfg in RCPS_MODELS.items():
        rcps = load_json(cfg["rcps"])
        direct = load_json(cfg["direct"])
        model_data[model_name] = {"rcps": rcps, "direct": direct, "cfg": cfg}
        print(f"  {model_name}: RCPS {len(get_targets(rcps))} targets, Direct {len(get_targets(direct))} targets")

    # Verify reconstruction
    print("\nVerifying RCPS reconstruction (a=6, rcps_full)...")
    for model_name, md in model_data.items():
        mismatches = verify_reconstruction(md["rcps"], eval_data, context_cache)
        if mismatches:
            print(f"  {model_name}: MISMATCH - {len(mismatches)} targets")
            for m in mismatches[:5]:
                print(f"    {m}")
            print("STOPPING: reconstruction mismatch before API calls")
            return 1
        else:
            print(f"  {model_name}: OK")

    if args.dry_run:
        print("\nDry run complete. No API calls made.")
        print(f"Anchor budgets: {ANCHOR_BUDGETS}")
        print(f"Models: {list(RCPS_MODELS.keys())}")
        return 0

    # Prepare judgment cache
    cache_path = RESULT_DIR / "candidate_judgment_cache.jsonl"
    judgment_cache: dict[str, dict] = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                if entry.get("judgment", {}).get("parse_status") == "ok":
                    judgment_cache[entry["cache_key"]] = entry
        print(f"Loaded {len(judgment_cache)} cached judgments")

    def get_cached_judgment(model: str, paper_idx: int, idea_text: str) -> dict | None:
        key = f"{model}|{paper_idx}|{sha256_text(idea_text.strip().lower())}"
        cached = judgment_cache.get(key)
        if cached and cached.get("judgment", {}).get("parse_status") == "ok":
            return cached
        return None

    def store_judgment(model: str, paper_idx: int, idea_text: str, judgment: dict):
        key = f"{model}|{paper_idx}|{sha256_text(idea_text.strip().lower())}"
        entry = {"cache_key": key, "model": model, "paper_idx": paper_idx, "judgment": judgment}
        judgment_cache[key] = entry
        with open(cache_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    anchor_csv = RESULT_DIR / "anchor_sensitivity_livejudge.csv"
    selector_csv = RESULT_DIR / "selector_ablation_livejudge.csv"
    portfolio_json = RESULT_DIR / "portfolio_results_livejudge.json"
    drift_csv = RESULT_DIR / "stored_vs_rejudge_drift.csv"

    anchor_fieldnames = [
        "model", "experiment_type", "variant", "anchor_slots", "selector_variant",
        "targets", "hits", "hit_at_10_percent",
        "direct_stored_hits", "new_hits_vs_stored_direct", "lost_hits_vs_stored_direct",
        "net_hits_vs_stored_direct", "exact_p_if_computable",
        "selected_idea_count_min", "selected_idea_count_median", "selected_idea_count_max",
        "anchor_hit_targets", "fill_hit_targets", "anchor_only_hit_targets",
        "fill_only_hit_targets", "both_anchor_and_fill_hit_targets",
        "input_tokens", "output_tokens",
    ]

    all_results = []
    drift_rows = []
    total_targets = 77 if args.full else args.smoke

    for model_name, md in model_data.items():
        configure_judge(model_name, args.request_timeout, args.sleep_seconds)
        rcps_data = md["rcps"]
        direct_data = md["direct"]

        direct_stored_hits = set()
        for t in get_targets(direct_data)[:total_targets]:
            if is_hit(t):
                direct_stored_hits.add(t.get("paper_idx", get_target_id(t)))

        targets = get_targets(rcps_data)[:total_targets]

        # Drift rejudge
        print(f"\n=== {model_name}: Drift rejudge ===")
        for stored_label, source_data in [("direct", direct_data), ("rcps", rcps_data)]:
            rejudge_hits = set()
            input_tokens = 0
            output_tokens = 0
            for t in get_targets(source_data)[:total_targets]:
                tid = get_target_id(t)
                pid = t.get("paper_idx", tid)
                ideas = t.get("generated_ideas", [])
                if not ideas:
                    continue
                title, contrib = judge_target_fields(t)
                portfolio = [{"idea_text": idea, "source": stored_label} for idea in ideas]
                hit, _, _, in_tok, out_tok = evaluate_portfolio(
                    model_name, pid, portfolio, title, contrib,
                    get_cached_judgment, store_judgment, args.sleep_seconds,
                )
                input_tokens += in_tok
                output_tokens += out_tok
                if hit:
                    rejudge_hits.add(pid)

            stored_hits_set = set()
            for t in get_targets(source_data)[:total_targets]:
                if (stored_label == "direct" and is_hit(t)) or (stored_label == "rcps" and is_hit(t)):
                    stored_hits_set.add(t.get("paper_idx", get_target_id(t)))

            drift_rows.append({
                "model": model_name,
                "source": stored_label,
                "stored_hits": len(stored_hits_set),
                "rejudge_hits": len(rejudge_hits),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            })
            print(f"  {stored_label}: stored={len(stored_hits_set)}, rejudge={len(rejudge_hits)}")

        # Anchor sensitivity
        print(f"\n=== {model_name}: Anchor sensitivity ===")
        for anchor_a in ANCHOR_BUDGETS:
            hits = 0
            new_hits = 0
            lost_hits = 0
            anchor_hit_set = set()
            fill_hit_set = set()
            idea_counts = []
            input_tokens = 0
            output_tokens = 0

            for t in targets:
                tid = get_target_id(t)
                pid = t.get("paper_idx", tid)
                direct_pool, bcs_pool = split_candidate_pool(t)
                context = build_context_for_target(tid, eval_data, context_cache, t)
                portfolio = build_portfolio(direct_pool, bcs_pool, context, anchor_a, "rcps_full")
                idea_counts.append(len(portfolio))

                title, contrib = judge_target_fields(t)
                target_hit, anchor_hit, fill_hit, in_tok, out_tok = evaluate_portfolio(
                    model_name, pid, portfolio, title, contrib,
                    get_cached_judgment, store_judgment, args.sleep_seconds,
                )
                input_tokens += in_tok
                output_tokens += out_tok

                if target_hit:
                    hits += 1
                if anchor_hit:
                    anchor_hit_set.add(pid)
                if fill_hit:
                    fill_hit_set.add(pid)

                was_direct_hit = pid in direct_stored_hits
                if target_hit and not was_direct_hit:
                    new_hits += 1
                elif not target_hit and was_direct_hit:
                    lost_hits += 1

            net = new_hits - lost_hits
            both = len(anchor_hit_set & fill_hit_set)
            ic_sorted = sorted(idea_counts)

            row = {
                "model": model_name,
                "experiment_type": "anchor_sensitivity",
                "variant": f"anchor_{anchor_a}",
                "anchor_slots": anchor_a,
                "selector_variant": "rcps_full",
                "targets": total_targets,
                "hits": hits,
                "hit_at_10_percent": round(hits / max(total_targets, 1) * 100, 2),
                "direct_stored_hits": len(direct_stored_hits),
                "new_hits_vs_stored_direct": new_hits,
                "lost_hits_vs_stored_direct": lost_hits,
                "net_hits_vs_stored_direct": net,
                "exact_p_if_computable": "",
                "selected_idea_count_min": min(idea_counts) if idea_counts else 0,
                "selected_idea_count_median": ic_sorted[len(ic_sorted)//2] if ic_sorted else 0,
                "selected_idea_count_max": max(idea_counts) if idea_counts else 0,
                "anchor_hit_targets": len(anchor_hit_set),
                "fill_hit_targets": len(fill_hit_set),
                "anchor_only_hit_targets": len(anchor_hit_set - fill_hit_set),
                "fill_only_hit_targets": len(fill_hit_set - anchor_hit_set),
                "both_anchor_and_fill_hit_targets": both,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            all_results.append(row)
            _write_csv(anchor_csv, anchor_fieldnames, [r for r in all_results if r["experiment_type"] == "anchor_sensitivity"])
            print(f"  a={anchor_a}: {hits}/{total_targets} = {row['hit_at_10_percent']}%")

        # Selector ablation
        print(f"\n=== {model_name}: Selector ablation ===")
        selector_variants = [
            ("rcps_full", 6, "rcps_full", 0),
            ("direct_prefix10_from_rcps_call", 10, "direct_prefix10_from_rcps_call", 0),
            ("no_anchor_fill10", 0, "no_anchor_fill10", 0),
            ("anchor6_topscore_no_diversity", 6, "anchor6_topscore_no_diversity", 0),
            ("anchor6_specificity_only", 6, "anchor6_specificity_only", 0),
            ("anchor6_grounding_only", 6, "anchor6_grounding_only", 0),
            ("anchor6_random_fill_seed0", 6, "anchor6_random_fill_seed0", 0),
            ("anchor6_random_fill_seed1", 6, "anchor6_random_fill_seed1", 1),
            ("anchor6_random_fill_seed2", 6, "anchor6_random_fill_seed2", 2),
        ]

        for variant_name, anchor_a, selector, seed in selector_variants:
            hits = 0
            new_hits = 0
            lost_hits = 0
            anchor_hit_set = set()
            fill_hit_set = set()
            idea_counts = []
            input_tokens = 0
            output_tokens = 0

            for t in targets:
                tid = get_target_id(t)
                pid = t.get("paper_idx", tid)
                direct_pool, bcs_pool = split_candidate_pool(t)
                context = build_context_for_target(tid, eval_data, context_cache, t)
                portfolio = build_portfolio(direct_pool, bcs_pool, context, anchor_a, selector, seed)
                idea_counts.append(len(portfolio))

                title, contrib = judge_target_fields(t)
                target_hit, anchor_hit, fill_hit, in_tok, out_tok = evaluate_portfolio(
                    model_name, pid, portfolio, title, contrib,
                    get_cached_judgment, store_judgment, args.sleep_seconds,
                )
                input_tokens += in_tok
                output_tokens += out_tok

                if target_hit:
                    hits += 1
                if anchor_hit:
                    anchor_hit_set.add(pid)
                if fill_hit:
                    fill_hit_set.add(pid)

                was_direct_hit = pid in direct_stored_hits
                if target_hit and not was_direct_hit:
                    new_hits += 1
                elif not target_hit and was_direct_hit:
                    lost_hits += 1

            net = new_hits - lost_hits
            both = len(anchor_hit_set & fill_hit_set)
            ic_sorted = sorted(idea_counts)

            row = {
                "model": model_name,
                "experiment_type": "selector_ablation",
                "variant": variant_name,
                "anchor_slots": anchor_a,
                "selector_variant": selector,
                "targets": total_targets,
                "hits": hits,
                "hit_at_10_percent": round(hits / max(total_targets, 1) * 100, 2),
                "direct_stored_hits": len(direct_stored_hits),
                "new_hits_vs_stored_direct": new_hits,
                "lost_hits_vs_stored_direct": lost_hits,
                "net_hits_vs_stored_direct": net,
                "exact_p_if_computable": "",
                "selected_idea_count_min": min(idea_counts) if idea_counts else 0,
                "selected_idea_count_median": ic_sorted[len(ic_sorted)//2] if ic_sorted else 0,
                "selected_idea_count_max": max(idea_counts) if idea_counts else 0,
                "anchor_hit_targets": len(anchor_hit_set),
                "fill_hit_targets": len(fill_hit_set),
                "anchor_only_hit_targets": len(anchor_hit_set - fill_hit_set),
                "fill_only_hit_targets": len(fill_hit_set - anchor_hit_set),
                "both_anchor_and_fill_hit_targets": both,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            all_results.append(row)
            _write_csv(selector_csv, anchor_fieldnames, [r for r in all_results if r["experiment_type"] == "selector_ablation"])
            print(f"  {variant_name}: {hits}/{total_targets} = {row['hit_at_10_percent']}%")

    # Write drift CSV
    with open(drift_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "source", "stored_hits", "rejudge_hits", "input_tokens", "output_tokens"],
        )
        writer.writeheader()
        writer.writerows(drift_rows)

    # Write portfolio JSON
    portfolio_data = {
        "timestamp": datetime.now().isoformat(),
        "models": list(RCPS_MODELS.keys()),
        "anchor_budgets": ANCHOR_BUDGETS,
        "total_targets": total_targets,
        "results": all_results,
    }
    portfolio_json.write_text(json.dumps(portfolio_data, indent=2, ensure_ascii=False))

    # Write summary
    _write_summary(all_results, drift_rows, total_targets)

    # Write manifest
    _write_manifest()

    print("\nDone. All outputs written to", RESULT_DIR)
    return 0


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(results: list[dict], drift_rows: list[dict], total_targets: int):
    path = RESULT_DIR / "summary.md"
    lines = [
        "# RCPS Anchor Sensitivity and Selector Ablation Summary",
        "",
        f"Generated: {datetime.now().isoformat()}",
        f"Total targets: {total_targets}",
        "",
        "## Anchor Sensitivity",
        "",
        "| Model | Anchors | Hits | Hit@10% | New | Lost | Net |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        if r["experiment_type"] == "anchor_sensitivity":
            lines.append(f"| {r['model']} | {r['anchor_slots']} | {r['hits']} | {r['hit_at_10_percent']}% | {r['new_hits_vs_stored_direct']} | {r['lost_hits_vs_stored_direct']} | {r['net_hits_vs_stored_direct']} |")

    lines.extend(["", "## Selector Ablation", "", "| Model | Variant | Hits | Hit@10% | New | Lost | Net |", "|---|---|---:|---:|---:|---:|---:|"])
    for r in results:
        if r["experiment_type"] == "selector_ablation":
            lines.append(f"| {r['model']} | {r['variant']} | {r['hits']} | {r['hit_at_10_percent']}% | {r['new_hits_vs_stored_direct']} | {r['lost_hits_vs_stored_direct']} | {r['net_hits_vs_stored_direct']} |")

    lines.extend(["", "## Stored vs Rejudge Drift", "", "| Model | Source | Stored Hits | Rejudge Hits |", "|---|---|---:|---:|"])
    for d in drift_rows:
        lines.append(f"| {d['model']} | {d['source']} | {d['stored_hits']} | {d['rejudge_hits']} |")

    path.write_text("\n".join(lines) + "\n")


def _write_manifest():
    import hashlib as hl
    def _hash(p):
        return hl.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else "missing"

    manifest = {
        "timestamp": datetime.now().isoformat(),
        "script_path": "scripts/45_rcps_anchor_selector_sensitivity.py",
        "script_sha256": _hash(PROJECT_ROOT / "scripts" / "45_rcps_anchor_selector_sensitivity.py"),
        "input_files": {},
        "env_vars_used": ["SJTU_BASE_URL", "SJTU_API_KEY", "GEMINI_BASE_URL", "GEMINI_API_KEY"],
        "no_new_generation": True,
        "no_exa_calls": True,
        "target_hidden_selection": True,
        "judge_after_selection_only": True,
    }
    for model_name, cfg in RCPS_MODELS.items():
        manifest["input_files"][f"{model_name}_rcps"] = str(cfg["rcps"])
        manifest["input_files"][f"{model_name}_direct"] = str(cfg["direct"])

    (RESULT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
