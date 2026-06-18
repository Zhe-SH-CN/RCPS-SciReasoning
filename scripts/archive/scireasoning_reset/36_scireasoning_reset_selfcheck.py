#!/usr/bin/env python3
"""
Local self-check for the Sci-Reasoning faithful reset.

No network calls and no model calls. This script checks that the reset runner is
wired to the paper/repository protocol before Claude Code spends API tokens.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_33 = PROJECT_ROOT / "scripts" / "33_scireasoning_faithful_reproduction.py"
SCRIPT_34 = PROJECT_ROOT / "scripts" / "34_scireasoning_faithful_methods.py"
SCRIPT_35 = PROJECT_ROOT / "scripts" / "35_audit_scireasoning_faithful.py"
PLAN_24 = PROJECT_ROOT / "Plan" / "24_SCIREASONING_FAITHFUL_REPRODUCTION_RESET.md"
PLAN_25 = PROJECT_ROOT / "Plan" / "25_CLAUDE_RUN_SCIREASONING_FAITHFUL_DIRECT.md"
PLAN_26 = PROJECT_ROOT / "Plan" / "26_CLAUDE_RUN_SCIREASONING_METHODS_AFTER_DIRECT.md"
PLAN_27 = PROJECT_ROOT / "Plan" / "27_CACHE_ONLY_SCIREASONING_RESET_MASTER.md"
PLAN_28 = PROJECT_ROOT / "Plan" / "28_CLAUDE_CACHE_DIRECT_SMOKE.md"
PLAN_29 = PROJECT_ROOT / "Plan" / "29_CLAUDE_CACHE_DIRECT_FULL.md"
PLAN_30 = PROJECT_ROOT / "Plan" / "30_CLAUDE_CACHE_METHOD_SMOKE.md"
PLAN_31 = PROJECT_ROOT / "Plan" / "31_CLAUDE_CACHE_METHOD_FULL.md"


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local Sci-Reasoning reset readiness")
    parser.add_argument("--require-api-deps", action="store_true", help="Fail if openai is not importable")
    args = parser.parse_args()

    issues: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {}

    for path in [SCRIPT_33, SCRIPT_34, SCRIPT_35, PLAN_24, PLAN_25, PLAN_26, PLAN_27, PLAN_28, PLAN_29, PLAN_30, PLAN_31]:
        if not path.exists():
            issues.append(f"missing_file:{path.relative_to(PROJECT_ROOT)}")

    if issues:
        print(json.dumps({"verdict": "FAIL", "issues": issues, "warnings": warnings}, indent=2))
        return 1

    faith = import_module(SCRIPT_33, "faith")
    import_module(SCRIPT_34, "methods")
    import_module(SCRIPT_35, "audit")
    script_33_text = SCRIPT_33.read_text()
    script_34_text = SCRIPT_34.read_text()
    if 'parser.add_argument("--context-source", default="cache", choices=["cache"]' not in script_33_text:
        issues.append("script33_context_source_default_not_cache_only")
    if 'parser.add_argument("--context-source", default="cache", choices=["cache"]' not in script_34_text:
        issues.append("script34_context_source_default_not_cache_only")
    forbidden_retrieval_refs = [
        "live" + "_exa",
        "EXA" + "_API_KEY",
        "exa" + "_py",
        "fetch_" + "live" + "_exa_context",
    ]
    for forbidden in forbidden_retrieval_refs:
        if forbidden in script_33_text:
            issues.append(f"script33_forbidden_live_retrieval_reference:{forbidden}")
        if forbidden in script_34_text:
            issues.append(f"script34_forbidden_live_retrieval_reference:{forbidden}")
    if 'parser.add_argument("--judge-max-tokens", type=int, default=4096)' not in script_33_text:
        issues.append("script33_judge_max_tokens_not_4096")

    malformed_judgment = """{
  "is_match": false,
  "confidence": 0.3,
  "reasoning": The generated idea is related but not aligned."
}"""
    recovered = faith.parse_json_response(malformed_judgment)
    if not isinstance(recovered, dict) or recovered.get("is_match") is not False or not recovered.get("_recovered_parse"):
        issues.append("paper_json_recovery_failed")

    eval_records = faith.load_eval_records(faith.DEFAULT_EVAL_DATA)
    summary["eval_records"] = len(eval_records)
    if len(eval_records) != 77:
        issues.append(f"eval_record_count_not_77:{len(eval_records)}")

    missing_required = []
    missing_preds = []
    min_preds = None
    for record in eval_records:
        if not record.get("target_id") or not record.get("title") or not record.get("contribution"):
            missing_required.append(record.get("target_id", "<missing_id>"))
        preds = faith.predecessor_titles(record)
        if not preds:
            missing_preds.append(record.get("target_id", "<missing_id>"))
        min_preds = len(preds) if min_preds is None else min(min_preds, len(preds))
    summary["min_predecessor_titles"] = min_preds
    if missing_required:
        issues.append(f"missing_required_fields:{','.join(missing_required[:10])}")
    if missing_preds:
        issues.append(f"missing_predecessor_titles:{','.join(missing_preds[:10])}")

    cache = faith.load_context_cache(faith.DEFAULT_CONTEXT_CACHE)
    missing_cache = [r["target_id"] for r in eval_records if r.get("title") not in cache]
    summary["cache_records"] = len(cache)
    summary["missing_cache_records"] = len(missing_cache)
    if missing_cache:
        warnings.append(f"missing_cache_records:{','.join(missing_cache[:10])}")

    usable_counts = []
    excluded_title = 0
    excluded_contribution = 0
    for record in eval_records:
        details = cache.get(record.get("title"), [])
        if not details:
            continue
        context, meta = faith.build_context(
            details,
            6000,
            record.get("title", ""),
            record.get("contribution", ""),
            True,
        )
        usable_counts.append(meta["usable_predecessors"])
        excluded_title += meta["excluded_target_title_contexts"]
        excluded_contribution += meta["excluded_target_contribution_contexts"]
        blob = context.lower()
        if record.get("title", "").lower() in blob:
            issues.append(f"cache_context_target_title_leak:{record.get('target_id')}")
        contribution = record.get("contribution", "").lower()
        if len(contribution) > 60 and contribution in blob:
            issues.append(f"cache_context_target_contribution_leak:{record.get('target_id')}")
    summary["cache_min_usable_predecessors_after_exclusion"] = min(usable_counts) if usable_counts else 0
    summary["excluded_target_title_contexts"] = excluded_title
    summary["excluded_target_contribution_contexts"] = excluded_contribution
    if usable_counts and min(usable_counts) < 1:
        issues.append("cache_context_has_zero_usable_predecessors")

    plan_texts = {
        "plan27": PLAN_27.read_text(),
        "plan28": PLAN_28.read_text(),
        "plan29": PLAN_29.read_text(),
        "plan30": PLAN_30.read_text(),
        "plan31": PLAN_31.read_text(),
    }
    live_context_source = "live" + "_exa"
    exa_option_prefix = "--" + "exa" + "-"
    exa_key_name = "EXA" + "_API_KEY"
    exa_package_name = "exa" + "_py"
    for name, text in plan_texts.items():
        if live_context_source in text or exa_option_prefix in text or exa_key_name in text or exa_package_name in text:
            issues.append(f"{name}_contains_live_retrieval_or_dependency")
    for required in [
        "--context-source cache",
        "--require-context-source cache",
        "--max-tokens 4096",
        "--judge-max-tokens 4096",
        "ctx-cache",
    ]:
        if required not in plan_texts["plan28"]:
            issues.append(f"plan28_missing:{required}")
    for required in ["--context-source cache", "--max-tokens 4096", "--judge-max-tokens 4096", "ctx-cache"]:
        if required not in plan_texts["plan29"]:
            issues.append(f"plan29_missing:{required}")
        if required not in plan_texts["plan30"]:
            issues.append(f"plan30_missing:{required}")
        if required not in plan_texts["plan31"]:
            issues.append(f"plan31_missing:{required}")

    package_status = {"openai": has_package("openai")}
    summary["package_status"] = package_status
    if args.require_api_deps:
        for name, ok in package_status.items():
            if not ok:
                issues.append(f"missing_python_package:{name}")
    else:
        for name, ok in package_status.items():
            if not ok:
                warnings.append(f"missing_python_package:{name}")

    output = {
        "verdict": "FAIL" if issues else "PASS",
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
