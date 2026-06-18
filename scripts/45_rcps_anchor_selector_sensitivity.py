#!/usr/bin/env python3
"""
RCPS anchor-budget sensitivity and selector/component ablation.

This script reuses existing RCPS candidate_pool data. It performs target-hidden
reselection and final author-repository-v4-style binary judging. It makes no
new idea-generation calls and no Exa calls.

Execution model:
  * one worker process per model row;
  * each model worker runs its own targets/variants serially;
  * each model has an independent judgment cache and resume state;
  * aggregate CSV/JSON/Markdown outputs are merged only after all model workers
    finish successfully.
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
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT38 = PROJECT_ROOT / "scripts" / "38_scireasoning_official_cache_exa.py"
SCRIPT39 = PROJECT_ROOT / "scripts" / "39_scireasoning_official_cache_methods.py"

RESULT_DIR = PROJECT_ROOT / "results" / "experiments" / "20260617_rcps_anchor_selector_parallel"
LOG_DIR = PROJECT_ROOT / "logs" / "20260617_rcps_anchor_selector_parallel"

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

ANCHOR_BUDGETS = [0, 2, 4, 6, 8, 10]

SELECTOR_VARIANTS = [
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

RESULT_FIELDNAMES = [
    "model", "experiment_type", "variant", "anchor_slots", "selector_variant",
    "targets", "hits", "hit_at_10_percent",
    "direct_stored_hits", "new_hits_vs_stored_direct", "lost_hits_vs_stored_direct",
    "net_hits_vs_stored_direct", "exact_p_if_computable",
    "selected_idea_count_min", "selected_idea_count_median", "selected_idea_count_max",
    "anchor_hit_targets", "fill_hit_targets", "anchor_only_hit_targets",
    "fill_only_hit_targets", "both_anchor_and_fill_hit_targets",
    "input_tokens", "output_tokens",
]

DRIFT_FIELDNAMES = [
    "model", "source", "stored_hits", "rejudge_hits", "input_tokens", "output_tokens",
]


def log(prefix: str, message: str) -> None:
    print(f"[{prefix}] {message}", flush=True)


def slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_eval_data() -> dict[str, dict]:
    path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
    rows = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                rows[rec["target_id"]] = rec
    return rows


def get_targets(data: dict) -> list[dict]:
    return data.get("targets", data.get("results", []))


def get_target_id(target: dict) -> str:
    return str(target.get("target_id", target.get("paper_idx", "")))


def is_hit(target: dict) -> bool:
    return bool(target.get("hit", target.get("hit_at_k", False)))


def candidate_text(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    return str(candidate.get("idea_text", ""))


def split_candidate_pool(target: dict) -> tuple[list[dict], list[dict]]:
    pool = target.get("candidate_pool", [])
    direct = [c for c in pool if c.get("source") == "direct_anchor"]
    bcs = [c for c in pool if c.get("source") == "bcs"]
    return direct, bcs


def build_context_for_target(s39, target_id: str, eval_data: dict, context_cache: dict, rcps_target: dict | None = None) -> str:
    if rcps_target and rcps_target.get("predecessor_details"):
        return s39.build_official_context(rcps_target["predecessor_details"])
    rec = eval_data.get(target_id, {})
    details = context_cache.get(rec.get("title", ""), [])
    if details:
        return s39.build_official_context(details)
    return ""


def select_diverse(s39, candidates: list[dict], context: str, k: int) -> list[dict]:
    return s39.select_diverse(candidates, context, k)


def select_top_score(s39, candidates: list[dict], context: str, k: int) -> list[dict]:
    scored = s39.score_candidates(candidates, context)
    return scored[:k]


def select_by_specificity(s39, candidates: list[dict], context: str, k: int) -> list[dict]:
    scored = s39.score_candidates(candidates, context)
    scored.sort(key=lambda x: x.get("selector_diagnostics", {}).get("specificity", 0), reverse=True)
    return scored[:k]


def select_by_grounding(s39, candidates: list[dict], context: str, k: int) -> list[dict]:
    scored = s39.score_candidates(candidates, context)
    scored.sort(key=lambda x: x.get("selector_diagnostics", {}).get("context_grounding", 0), reverse=True)
    return scored[:k]


def select_random(candidates: list[dict], k: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    pool = list(candidates)
    rng.shuffle(pool)
    return pool[:k]


def build_portfolio(
    s39,
    direct: list[dict],
    bcs: list[dict],
    context: str,
    anchor_slots: int,
    selector: str,
    seed: int = 0,
) -> list[dict]:
    anchors = direct[:anchor_slots]
    fill_k = 10 - len(anchors)
    if fill_k <= 0:
        return anchors[:10]

    if selector in ("rcps_full", "default"):
        fill = select_diverse(s39, bcs, context, fill_k)
    elif selector == "no_anchor_fill10":
        return select_diverse(s39, bcs, context, 10)
    elif selector == "anchor6_topscore_no_diversity":
        fill = select_top_score(s39, bcs, context, fill_k)
    elif selector == "anchor6_specificity_only":
        fill = select_by_specificity(s39, bcs, context, fill_k)
    elif selector == "anchor6_grounding_only":
        fill = select_by_grounding(s39, bcs, context, fill_k)
    elif selector.startswith("anchor6_random_fill_seed"):
        fill = select_random(bcs, fill_k, seed)
    elif selector == "direct_prefix10_from_rcps_call":
        return direct[:10]
    else:
        fill = select_diverse(s39, bcs, context, fill_k)
    return anchors + fill


def verify_reconstruction(s39, rcps_data: dict, eval_data: dict, context_cache: dict) -> list[str]:
    mismatches = []
    for target in get_targets(rcps_data):
        tid = get_target_id(target)
        stored = target.get("generated_ideas", [])
        if not stored:
            continue
        direct, bcs = split_candidate_pool(target)
        if not direct and not bcs:
            continue
        context = build_context_for_target(s39, tid, eval_data, context_cache, target)
        reconstructed = build_portfolio(s39, direct, bcs, context, 6, "rcps_full")
        if len(reconstructed) != len(stored):
            mismatches.append(f"{tid}: len mismatch {len(reconstructed)} vs {len(stored)}")
            continue
        for idx, (recon, saved) in enumerate(zip(reconstructed, stored)):
            if candidate_text(recon).strip() != candidate_text(saved).strip():
                mismatches.append(f"{tid}: idea {idx} mismatch")
                break
    return mismatches


def configure_judge(s38, model_name: str, request_timeout: float, sleep_seconds: float) -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    if not api_key:
        raise RuntimeError("missing GEMINI_API_KEY or OPENAI_API_KEY")
    if not base_url:
        raise RuntimeError("missing GEMINI_BASE_URL or OPENAI_BASE_URL")
    s38.OPENAI_API_KEY = api_key
    s38.OPENAI_BASE_URL = base_url
    s38.OPENAI_MODEL = model_name
    s38.REQUEST_TIMEOUT_SECONDS = request_timeout
    s38.MODEL_SLEEP_SECONDS = sleep_seconds


def judge_target_fields(target: dict) -> tuple[str, str]:
    title = str(target.get("paper_title") or target.get("title") or "").strip()
    contribution = str(target.get("contribution") or "").strip()
    if not title or not contribution:
        raise RuntimeError(f"missing final-judge target fields for paper_idx={target.get('paper_idx')}")
    return title, contribution


def judge_idea_with_s38(s38, idea_text: str, title: str, contribution: str) -> dict:
    attempt = 0
    while True:
        try:
            is_match, in_tok, out_tok = s38.judge_similarity(idea_text, title, contribution)
            return {
                "is_match": is_match,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "parse_status": "ok",
            }
        except Exception as exc:
            error = str(exc).lower()
            transient = ["429", "rate", "timeout", "time-out", "connection", "reset", "502", "503", "504"]
            if any(token in error for token in transient):
                attempt += 1
                safe = str(exc)[:200]
                if hasattr(s38, "sanitize_api_error_text"):
                    safe = s38.sanitize_api_error_text(str(exc))[:200]
                print(f"Transient judge error attempt={attempt}; sleeping 10s; error={safe}", flush=True)
                time.sleep(10)
                continue
            safe = str(exc)[:200]
            if hasattr(s38, "sanitize_api_error_text"):
                safe = s38.sanitize_api_error_text(str(exc))[:200]
            raise RuntimeError(f"non-transient judge error: {safe}") from exc


def load_judgment_cache(cache_path: Path) -> dict[str, dict]:
    cache = {}
    if not cache_path.exists():
        return cache
    for line in cache_path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("judgment", {}).get("parse_status") == "ok":
            cache[entry["cache_key"]] = entry
    return cache


def make_cache_key(model: str, paper_idx: Any, idea_text: str) -> str:
    return f"{model}|{paper_idx}|{sha256_text(idea_text.strip().lower())}"


def evaluate_portfolio(
    s38,
    model_name: str,
    paper_idx: Any,
    portfolio: list[Any],
    title: str,
    contribution: str,
    judgment_cache: dict[str, dict],
    cache_path: Path,
    sleep_seconds: float,
) -> tuple[bool, bool, bool, int, int]:
    target_hit = False
    anchor_hit = False
    fill_hit = False
    input_tokens = 0
    output_tokens = 0

    for idea in portfolio:
        idea_text = candidate_text(idea)
        key = make_cache_key(model_name, paper_idx, idea_text)
        cached = judgment_cache.get(key)
        if cached and cached.get("judgment", {}).get("parse_status") == "ok":
            judgment = cached["judgment"]
        else:
            judgment = judge_idea_with_s38(s38, idea_text, title, contribution)
            entry = {"cache_key": key, "model": model_name, "paper_idx": paper_idx, "judgment": judgment}
            judgment_cache[key] = entry
            with open(cache_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        input_tokens += int(judgment.get("input_tokens", 0) or 0)
        output_tokens += int(judgment.get("output_tokens", 0) or 0)
        if judgment.get("is_match"):
            target_hit = True
            if isinstance(idea, dict) and idea.get("source") == "direct_anchor":
                anchor_hit = True
            else:
                fill_hit = True
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return target_hit, anchor_hit, fill_hit, input_tokens, output_tokens


def empty_model_state(model_name: str, total_targets: int) -> dict:
    return {
        "model": model_name,
        "total_targets": total_targets,
        "timestamp": datetime.now().isoformat(),
        "completed_units": [],
        "results": [],
        "drift_rows": [],
    }


def load_model_state(path: Path, model_name: str, total_targets: int) -> dict:
    if not path.exists():
        return empty_model_state(model_name, total_targets)
    state = json.loads(path.read_text())
    if state.get("model") != model_name or state.get("total_targets") != total_targets:
        return empty_model_state(model_name, total_targets)
    state.setdefault("completed_units", [])
    state.setdefault("results", [])
    state.setdefault("drift_rows", [])
    return state


def save_model_state(path: Path, state: dict) -> None:
    state["timestamp"] = datetime.now().isoformat()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.replace(path)


def get_completed_row(state: dict, unit_key: str) -> dict | None:
    for row in state.get("results", []):
        if row.get("unit_key") == unit_key:
            return row
    return None


def get_completed_drift(state: dict, unit_key: str) -> dict | None:
    for row in state.get("drift_rows", []):
        if row.get("unit_key") == unit_key:
            return row
    return None


def append_completed_result(state: dict, unit_key: str, row: dict) -> None:
    state["completed_units"] = [u for u in state.get("completed_units", []) if u != unit_key]
    state["results"] = [r for r in state.get("results", []) if r.get("unit_key") != unit_key]
    state["completed_units"].append(unit_key)
    row = dict(row)
    row["unit_key"] = unit_key
    state["results"].append(row)


def append_completed_drift(state: dict, unit_key: str, row: dict) -> None:
    state["completed_units"] = [u for u in state.get("completed_units", []) if u != unit_key]
    state["drift_rows"] = [r for r in state.get("drift_rows", []) if r.get("unit_key") != unit_key]
    state["completed_units"].append(unit_key)
    row = dict(row)
    row["unit_key"] = unit_key
    state["drift_rows"].append(row)


def evaluate_variant(
    s38,
    s39,
    model_name: str,
    targets: list[dict],
    eval_data: dict,
    context_cache: dict,
    direct_stored_hits: set[Any],
    judgment_cache: dict[str, dict],
    cache_path: Path,
    total_targets: int,
    experiment_type: str,
    variant_name: str,
    anchor_slots: int,
    selector: str,
    seed: int,
    sleep_seconds: float,
) -> dict:
    hits = 0
    new_hits = 0
    lost_hits = 0
    anchor_hit_set = set()
    fill_hit_set = set()
    idea_counts = []
    input_tokens = 0
    output_tokens = 0

    for target_index, target in enumerate(targets, start=1):
        tid = get_target_id(target)
        pid = target.get("paper_idx", tid)
        direct_pool, bcs_pool = split_candidate_pool(target)
        context = build_context_for_target(s39, tid, eval_data, context_cache, target)
        portfolio = build_portfolio(s39, direct_pool, bcs_pool, context, anchor_slots, selector, seed)
        idea_counts.append(len(portfolio))

        title, contribution = judge_target_fields(target)
        target_hit, anchor_hit, fill_hit, in_tok, out_tok = evaluate_portfolio(
            s38, model_name, pid, portfolio, title, contribution,
            judgment_cache, cache_path, sleep_seconds,
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

        if target_index % 10 == 0 or target_index == total_targets:
            log(model_name, f"{variant_name}: {target_index}/{total_targets} targets judged")

    counts = sorted(idea_counts)
    both = len(anchor_hit_set & fill_hit_set)
    return {
        "model": model_name,
        "experiment_type": experiment_type,
        "variant": variant_name,
        "anchor_slots": anchor_slots,
        "selector_variant": selector,
        "targets": total_targets,
        "hits": hits,
        "hit_at_10_percent": round(hits / max(total_targets, 1) * 100, 2),
        "direct_stored_hits": len(direct_stored_hits),
        "new_hits_vs_stored_direct": new_hits,
        "lost_hits_vs_stored_direct": lost_hits,
        "net_hits_vs_stored_direct": new_hits - lost_hits,
        "exact_p_if_computable": "",
        "selected_idea_count_min": min(idea_counts) if idea_counts else 0,
        "selected_idea_count_median": counts[len(counts) // 2] if counts else 0,
        "selected_idea_count_max": max(idea_counts) if idea_counts else 0,
        "anchor_hit_targets": len(anchor_hit_set),
        "fill_hit_targets": len(fill_hit_set),
        "anchor_only_hit_targets": len(anchor_hit_set - fill_hit_set),
        "fill_only_hit_targets": len(fill_hit_set - anchor_hit_set),
        "both_anchor_and_fill_hit_targets": both,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def evaluate_drift(
    s38,
    model_name: str,
    source_label: str,
    source_data: dict,
    judgment_cache: dict[str, dict],
    cache_path: Path,
    total_targets: int,
    sleep_seconds: float,
) -> dict:
    rejudge_hits = set()
    stored_hits = set()
    input_tokens = 0
    output_tokens = 0

    for target_index, target in enumerate(get_targets(source_data)[:total_targets], start=1):
        tid = get_target_id(target)
        pid = target.get("paper_idx", tid)
        if is_hit(target):
            stored_hits.add(pid)
        ideas = target.get("generated_ideas", [])
        if not ideas:
            continue
        title, contribution = judge_target_fields(target)
        portfolio = [{"idea_text": idea, "source": source_label} for idea in ideas]
        hit, _, _, in_tok, out_tok = evaluate_portfolio(
            s38, model_name, pid, portfolio, title, contribution,
            judgment_cache, cache_path, sleep_seconds,
        )
        input_tokens += in_tok
        output_tokens += out_tok
        if hit:
            rejudge_hits.add(pid)

        if target_index % 10 == 0 or target_index == total_targets:
            log(model_name, f"drift/{source_label}: {target_index}/{total_targets} targets judged")

    return {
        "model": model_name,
        "source": source_label,
        "stored_hits": len(stored_hits),
        "rejudge_hits": len(rejudge_hits),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def run_model_worker(
    model_name: str,
    cfg: dict[str, str],
    total_targets: int,
    request_timeout: float,
    sleep_seconds: float,
    result_dir: str,
) -> dict:
    result_path = Path(result_dir)
    result_path.mkdir(parents=True, exist_ok=True)

    load_dotenv()
    slug = slugify(model_name)
    s38 = load_module(SCRIPT38, f"s38_{slug}")
    s39 = load_module(SCRIPT39, f"s39_{slug}")
    configure_judge(s38, model_name, request_timeout, sleep_seconds)

    eval_data = load_eval_data()
    context_cache, _ = s38.load_context_cache(s38.DEFAULT_CONTEXT_CACHE)
    rcps_data = load_json(Path(cfg["rcps"]))
    direct_data = load_json(Path(cfg["direct"]))

    mismatches = verify_reconstruction(s39, rcps_data, eval_data, context_cache)
    if mismatches:
        raise RuntimeError(f"{model_name} reconstruction mismatch: {mismatches[:5]}")

    state_path = result_path / f"model_{slug}_state.json"
    cache_path = result_path / f"candidate_judgment_cache_{slug}.jsonl"
    state = load_model_state(state_path, model_name, total_targets)
    judgment_cache = load_judgment_cache(cache_path)

    log(model_name, f"loaded {len(judgment_cache)} cached judgments; completed units={len(state['completed_units'])}")

    direct_stored_hits = {
        target.get("paper_idx", get_target_id(target))
        for target in get_targets(direct_data)[:total_targets]
        if is_hit(target)
    }
    targets = get_targets(rcps_data)[:total_targets]

    for source_label, source_data in [("direct", direct_data), ("rcps", rcps_data)]:
        unit_key = f"drift:{source_label}"
        if get_completed_drift(state, unit_key):
            log(model_name, f"resume skip {unit_key}")
            continue
        row = evaluate_drift(
            s38, model_name, source_label, source_data, judgment_cache,
            cache_path, total_targets, sleep_seconds,
        )
        append_completed_drift(state, unit_key, row)
        save_model_state(state_path, state)
        log(model_name, f"{unit_key}: stored={row['stored_hits']}, rejudge={row['rejudge_hits']}")

    for anchor_slots in ANCHOR_BUDGETS:
        variant_name = f"anchor_{anchor_slots}"
        unit_key = f"anchor_sensitivity:{variant_name}"
        if get_completed_row(state, unit_key):
            log(model_name, f"resume skip {unit_key}")
            continue
        row = evaluate_variant(
            s38, s39, model_name, targets, eval_data, context_cache, direct_stored_hits,
            judgment_cache, cache_path, total_targets,
            "anchor_sensitivity", variant_name, anchor_slots, "rcps_full", 0,
            sleep_seconds,
        )
        append_completed_result(state, unit_key, row)
        save_model_state(state_path, state)
        log(model_name, f"{variant_name}: {row['hits']}/{total_targets} = {row['hit_at_10_percent']}%")

    for variant_name, anchor_slots, selector, seed in SELECTOR_VARIANTS:
        unit_key = f"selector_ablation:{variant_name}"
        if get_completed_row(state, unit_key):
            log(model_name, f"resume skip {unit_key}")
            continue
        row = evaluate_variant(
            s38, s39, model_name, targets, eval_data, context_cache, direct_stored_hits,
            judgment_cache, cache_path, total_targets,
            "selector_ablation", variant_name, anchor_slots, selector, seed,
            sleep_seconds,
        )
        append_completed_result(state, unit_key, row)
        save_model_state(state_path, state)
        log(model_name, f"{variant_name}: {row['hits']}/{total_targets} = {row['hit_at_10_percent']}%")

    save_model_state(state_path, state)
    return state


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ordered_rows(states: list[dict]) -> tuple[list[dict], list[dict]]:
    state_by_model = {state["model"]: state for state in states}
    result_rows = []
    drift_rows = []
    for model_name in RCPS_MODELS:
        state = state_by_model.get(model_name)
        if not state:
            continue
        for row in state.get("results", []):
            clean = {k: v for k, v in row.items() if k != "unit_key"}
            result_rows.append(clean)
        for row in state.get("drift_rows", []):
            clean = {k: v for k, v in row.items() if k != "unit_key"}
            drift_rows.append(clean)

    result_rank = {
        **{f"anchor_sensitivity:anchor_{a}": i for i, a in enumerate(ANCHOR_BUDGETS)},
        **{f"selector_ablation:{name}": 100 + i for i, (name, _, _, _) in enumerate(SELECTOR_VARIANTS)},
    }

    def result_key(row: dict) -> tuple[int, int]:
        model_rank = list(RCPS_MODELS).index(row["model"])
        key = f"{row['experiment_type']}:{row['variant']}"
        return model_rank, result_rank.get(key, 999)

    source_rank = {"direct": 0, "rcps": 1}

    def drift_key(row: dict) -> tuple[int, int]:
        return list(RCPS_MODELS).index(row["model"]), source_rank.get(row["source"], 99)

    return sorted(result_rows, key=result_key), sorted(drift_rows, key=drift_key)


def write_summary(result_dir: Path, results: list[dict], drift_rows: list[dict], total_targets: int) -> None:
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
    for row in results:
        if row["experiment_type"] == "anchor_sensitivity":
            lines.append(
                f"| {row['model']} | {row['anchor_slots']} | {row['hits']} | "
                f"{row['hit_at_10_percent']}% | {row['new_hits_vs_stored_direct']} | "
                f"{row['lost_hits_vs_stored_direct']} | {row['net_hits_vs_stored_direct']} |"
            )

    lines.extend([
        "",
        "## Selector Ablation",
        "",
        "| Model | Variant | Hits | Hit@10% | New | Lost | Net |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in results:
        if row["experiment_type"] == "selector_ablation":
            lines.append(
                f"| {row['model']} | {row['variant']} | {row['hits']} | "
                f"{row['hit_at_10_percent']}% | {row['new_hits_vs_stored_direct']} | "
                f"{row['lost_hits_vs_stored_direct']} | {row['net_hits_vs_stored_direct']} |"
            )

    lines.extend([
        "",
        "## Stored vs Rejudge Drift",
        "",
        "| Model | Source | Stored Hits | Rejudge Hits |",
        "|---|---|---:|---:|",
    ])
    for row in drift_rows:
        lines.append(f"| {row['model']} | {row['source']} | {row['stored_hits']} | {row['rejudge_hits']} |")

    (result_dir / "summary.md").write_text("\n".join(lines) + "\n")


def write_manifest(result_dir: Path, total_targets: int, states: list[dict]) -> None:
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "script_path": "scripts/45_rcps_anchor_selector_sensitivity.py",
        "script_sha256": sha256_file(PROJECT_ROOT / "scripts" / "45_rcps_anchor_selector_sensitivity.py"),
        "result_dir": str(result_dir),
        "model_level_parallel": True,
        "model_internal_serial": True,
        "resume_state_files": [f"model_{slugify(name)}_state.json" for name in RCPS_MODELS],
        "total_targets": total_targets,
        "input_files": {},
        "env_vars_used": ["GEMINI_BASE_URL", "GEMINI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY"],
        "no_new_generation": True,
        "no_exa_calls": True,
        "target_hidden_selection": True,
        "judge_after_selection_only": True,
        "completed_models": [state["model"] for state in states],
    }
    for model_name, cfg in RCPS_MODELS.items():
        manifest["input_files"][f"{model_name}_rcps"] = str(cfg["rcps"])
        manifest["input_files"][f"{model_name}_direct"] = str(cfg["direct"])
    (result_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def write_aggregate_outputs(result_dir: Path, states: list[dict], total_targets: int) -> None:
    results, drift_rows = ordered_rows(states)
    anchor_rows = [row for row in results if row["experiment_type"] == "anchor_sensitivity"]
    selector_rows = [row for row in results if row["experiment_type"] == "selector_ablation"]

    write_csv(result_dir / "anchor_sensitivity_livejudge.csv", RESULT_FIELDNAMES, anchor_rows)
    write_csv(result_dir / "selector_ablation_livejudge.csv", RESULT_FIELDNAMES, selector_rows)
    write_csv(result_dir / "stored_vs_rejudge_drift.csv", DRIFT_FIELDNAMES, drift_rows)

    portfolio = {
        "timestamp": datetime.now().isoformat(),
        "models": list(RCPS_MODELS.keys()),
        "anchor_budgets": ANCHOR_BUDGETS,
        "selector_variants": [name for name, _, _, _ in SELECTOR_VARIANTS],
        "total_targets": total_targets,
        "results": results,
        "drift_rows": drift_rows,
    }
    (result_dir / "portfolio_results_livejudge.json").write_text(json.dumps(portfolio, indent=2, ensure_ascii=False))
    write_summary(result_dir, results, drift_rows, total_targets)
    write_manifest(result_dir, total_targets, states)


def fresh_output_dir(result_dir: Path) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    patterns = [
        "candidate_judgment_cache_*.jsonl",
        "model_*_state.json",
        "model_*_state.json.tmp",
        "anchor_sensitivity_livejudge.csv",
        "selector_ablation_livejudge.csv",
        "stored_vs_rejudge_drift.csv",
        "portfolio_results_livejudge.json",
        "summary.md",
        "manifest.json",
    ]
    for pattern in patterns:
        for path in result_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def dry_run(models: list[str], total_targets: int) -> int:
    load_dotenv()
    eval_data = load_eval_data()
    s38 = load_module(SCRIPT38, "s38_dryrun")
    s39 = load_module(SCRIPT39, "s39_dryrun")
    context_cache, _ = s38.load_context_cache(s38.DEFAULT_CONTEXT_CACHE)
    print(f"Loaded {len(eval_data)} eval records, {len(context_cache)} cache records")
    for model_name in models:
        cfg = RCPS_MODELS[model_name]
        rcps = load_json(cfg["rcps"])
        direct = load_json(cfg["direct"])
        print(f"{model_name}: RCPS {len(get_targets(rcps))} targets, Direct {len(get_targets(direct))} targets")
        mismatches = verify_reconstruction(s39, rcps, eval_data, context_cache)
        if mismatches:
            print(f"{model_name}: reconstruction mismatch")
            for mismatch in mismatches[:5]:
                print(f"  {mismatch}")
            return 1
        print(f"{model_name}: reconstruction OK; planned targets={total_targets}")
    print(f"Output dir: {RESULT_DIR}")
    print("Dry run complete. No API calls made.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", type=int, default=0)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--fresh", action="store_true", help="clear the new parallel output directory before running")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--request-timeout", type=float, default=240.0)
    parser.add_argument("--parallel-workers", type=int, default=3)
    parser.add_argument("--models", nargs="*", choices=list(RCPS_MODELS.keys()), default=list(RCPS_MODELS.keys()))
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    args = parse_args()
    if args.full:
        total_targets = 77
    elif args.smoke > 0:
        total_targets = args.smoke
    else:
        total_targets = 3

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if args.fresh and not args.dry_run:
        fresh_output_dir(RESULT_DIR)

    if args.dry_run:
        return dry_run(args.models, total_targets)

    workers = max(1, min(args.parallel_workers, len(args.models)))
    print(f"Running {len(args.models)} model rows with {workers} parallel workers; total_targets={total_targets}")
    print(f"Output dir: {RESULT_DIR}")

    states = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                run_model_worker,
                model_name,
                {k: str(v) for k, v in RCPS_MODELS[model_name].items()},
                total_targets,
                args.request_timeout,
                args.sleep_seconds,
                str(RESULT_DIR),
            ): model_name
            for model_name in args.models
        }
        for future in as_completed(futures):
            model_name = futures[future]
            try:
                state = future.result()
            except Exception as exc:
                print(f"[{model_name}] FAILED: {exc}", flush=True)
                raise
            states.append(state)
            print(f"[{model_name}] complete", flush=True)

    if len(states) != len(args.models):
        raise RuntimeError(f"only {len(states)}/{len(args.models)} model rows completed")

    write_aggregate_outputs(RESULT_DIR, states, total_targets)
    print(f"Done. Aggregate outputs written to {RESULT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
