#!/usr/bin/env python3
"""
Static protocol audit for scripts/39_scireasoning_official_cache_methods.py.

This does not execute model calls. It checks that the method runner:
- loads scripts/38 as the official runner;
- uses scripts/38 parser and binary judge functions;
- keeps target title/contribution out of candidate-generation functions;
- records method-output provenance fields required by scripts/40 audit.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METHOD_SCRIPT = PROJECT_ROOT / "scripts" / "39_scireasoning_official_cache_methods.py"


FORBIDDEN_IN_GENERATORS = {
    "paper",
    "paper_data",
    "paper_title",
    "contribution",
    "ground_truth",
    "target_title",
    "target_contribution",
}


def attr_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = attr_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return attr_name(node.value)
    return ""


def function_defs(tree):
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def calls_function(func: ast.FunctionDef, call_name: str) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and attr_name(node.func) == call_name:
            return True
    return False


def identifiers_in_function(func: ast.FunctionDef) -> set[str]:
    names = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lower = node.value.lower()
            for token in FORBIDDEN_IN_GENERATORS:
                if token in lower:
                    names.add(token)
    return names


def audit():
    source = METHOD_SCRIPT.read_text()
    tree = ast.parse(source)
    funcs = function_defs(tree)
    issues = []

    if "SCRIPT38_PATH" not in source or "38_scireasoning_official_cache_exa.py" not in source:
        issues.append("missing_script38_path")

    call_generation = funcs.get("call_generation")
    if call_generation is None:
        issues.append("missing_call_generation_function")
    else:
        if not calls_function(call_generation, "mod.call_openai_api"):
            issues.append("call_generation_does_not_use_script38_call_openai_api")
        if not calls_function(call_generation, "mod.parse_ideas_from_response"):
            issues.append("call_generation_does_not_use_script38_parser")

    evaluate_selected = funcs.get("evaluate_selected")
    if evaluate_selected is None:
        issues.append("missing_evaluate_selected_function")
    else:
        if not calls_function(evaluate_selected, "mod.judge_similarity"):
            issues.append("evaluate_selected_does_not_use_script38_judge_similarity")

    generate_rcps = funcs.get("generate_rcps")
    if generate_rcps is None:
        issues.append("missing_generate_rcps_function")
    else:
        if not calls_function(generate_rcps, "mod.generate_research_ideas"):
            issues.append("rcps_does_not_use_script38_direct_generation_for_anchors")
        if not calls_function(generate_rcps, "mod.parse_ideas_from_response"):
            issues.append("rcps_does_not_use_script38_parser_for_anchors")

    for name in ["generate_bcs", "generate_pgcr", "generate_se_bcs", "generate_rcps"]:
        func = funcs.get(name)
        if func is None:
            issues.append(f"missing_{name}")
            continue
        identifiers = identifiers_in_function(func)
        forbidden = sorted(identifiers & FORBIDDEN_IN_GENERATORS)
        if forbidden:
            issues.append(f"{name}_uses_forbidden_target_identifiers:{','.join(forbidden)}")

    required_metadata = [
        '"evaluation_protocol": "official_v4_binary_judge_hit_at_k"',
        '"official_runner": str(SCRIPT38_PATH)',
        '"official_parser_function": "parse_ideas_from_response"',
        '"official_judge_function": "judge_similarity"',
        '"method_scope": "candidate_generation_and_target_hidden_selection_only"',
    ]
    for item in required_metadata:
        if item not in source:
            issues.append(f"missing_output_metadata:{item}")

    report = {
        "verdict": "PASS" if not issues else "FAIL",
        "script": str(METHOD_SCRIPT),
        "issues": issues,
        "checked_functions": [
            "call_generation",
            "generate_bcs",
            "generate_pgcr",
            "generate_se_bcs",
            "generate_rcps",
            "evaluate_selected",
        ],
    }
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(audit())
