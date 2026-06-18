#!/usr/bin/env python3
"""
Audit the clean-context GLM-5.1 Direct-10 self-judge evaluation.

This is a local verifier. It makes no API calls.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1"

DEFAULT_GENERATION = EXP_DIR / "generation_direct10_glm-51_targethidden-cleanctx_77t_20260614.json"
DEFAULT_EVALUATION = EXP_DIR / "evaluation_direct10_glm-51_glm-51_selfjudge_cleanctx_77t_20260614.json"
DEFAULT_AUDIT_JSON = PROJECT_ROOT / "results" / "post_submission_glm51_selfjudge_audit_2026-06-14.json"
DEFAULT_AUDIT_MD = PROJECT_ROOT / "results" / "post_submission_glm51_selfjudge_audit_2026-06-14.md"
DEFAULT_MANIFEST = EXP_DIR / "manifest_20260614.json"

EXPECTED_TARGETS = 77
EXPECTED_IDEAS_PER_TARGET = 10
EXPECTED_JUDGMENTS = EXPECTED_TARGETS * EXPECTED_IDEAS_PER_TARGET

SECRET_PATTERNS = [
    ("secret_env_name", re.compile(r"\b(?:SJTU_API_KEY|XIAOMI_MIMO_API_KEY|OPENAI_API_KEY)\b")),
    (
        "key_assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|authorization|bearer)\b\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,}"),
    ),
    ("sk_like_key", re.compile(r"\b(?:sk|sk-proj|mimo|sjtu)-[A-Za-z0-9._\-]{16,}\b")),
]
LOCAL_PATH_RE = re.compile(r"(/home/[^\s\"']+|/Users/[^\s\"']+|[A-Za-z]:\\Users\\[^\s\"']+)")


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def add_issue(issues: list[dict], severity: str, code: str, detail: str) -> None:
    issues.append({"severity": severity, "code": code, "detail": detail})


def scan_text(path: Path, issues: list[dict]) -> None:
    text = path.read_text(errors="replace")
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            add_issue(issues, "fail", name, f"Sensitive-looking token pattern found in {path.name}")
    if LOCAL_PATH_RE.search(text):
        add_issue(issues, "fail", "local_path", f"Local absolute path found in {path.name}")


def audit_generation(generation: dict, issues: list[dict]) -> dict[str, dict]:
    if generation.get("completed") != EXPECTED_TARGETS:
        add_issue(issues, "fail", "generation_completed", f"Expected 77, found {generation.get('completed')}")
    if generation.get("total_ideas") != EXPECTED_JUDGMENTS:
        add_issue(issues, "fail", "generation_total_ideas", f"Expected 770, found {generation.get('total_ideas')}")
    if generation.get("generation_parse_rate") != 100.0:
        add_issue(issues, "fail", "generation_parse_rate", f"Expected 100.0, found {generation.get('generation_parse_rate')}")
    if generation.get("any_leakage_detected") is not False:
        add_issue(issues, "fail", "generation_leakage_flag", "Generation artifact did not report any_leakage_detected=false")

    target_map = {}
    for target in generation.get("targets", []):
        target_id = target.get("target_id")
        if not target_id:
            add_issue(issues, "fail", "generation_missing_target_id", "A generation target lacks target_id")
            continue
        if target_id in target_map:
            add_issue(issues, "fail", "generation_duplicate_target", target_id)
        target_map[target_id] = target

        if "target_title" in target or "target_contribution" in target or "contribution_source" in target:
            add_issue(issues, "fail", "target_visible_generation_field", target_id)
        if target.get("target_visible_metadata_stored") is not False:
            add_issue(issues, "fail", "target_visible_metadata_stored", target_id)
        if target.get("leakage_issues"):
            add_issue(issues, "fail", "generation_target_leakage_issues", target_id)
        if target.get("generation", {}).get("parse_status") != "ok":
            add_issue(issues, "fail", "generation_parse_status", target_id)
        if len(target.get("generated_ideas", [])) != EXPECTED_IDEAS_PER_TARGET:
            add_issue(
                issues,
                "fail",
                "generation_idea_count",
                f"{target_id}: {len(target.get('generated_ideas', []))}",
            )
        if target.get("judgments"):
            add_issue(issues, "fail", "judge_data_inside_generation", target_id)

    if len(target_map) != EXPECTED_TARGETS:
        add_issue(issues, "fail", "generation_unique_targets", f"Expected 77, found {len(target_map)}")
    return target_map


def audit_evaluation(evaluation: dict, generation_map: dict[str, dict], issues: list[dict]) -> dict:
    targets = evaluation.get("targets", [])
    target_ids = [t.get("target_id") for t in targets]
    unique_ids = {tid for tid in target_ids if tid}
    status_counts = Counter()
    hit_count = 0
    judgment_count = 0
    target_parse_ok_counts = {}

    if evaluation.get("completed") != EXPECTED_TARGETS:
        add_issue(issues, "fail", "evaluation_completed", f"Expected 77, found {evaluation.get('completed')}")
    if len(targets) != EXPECTED_TARGETS:
        add_issue(issues, "fail", "evaluation_target_records", f"Expected 77, found {len(targets)}")
    if len(unique_ids) != EXPECTED_TARGETS:
        add_issue(issues, "fail", "evaluation_unique_targets", f"Expected 77, found {len(unique_ids)}")
    if set(generation_map) != unique_ids:
        missing = sorted(set(generation_map) - unique_ids)
        extra = sorted(unique_ids - set(generation_map))
        add_issue(issues, "fail", "target_id_mismatch", f"missing={missing[:10]} extra={extra[:10]}")

    for target in targets:
        target_id = target.get("target_id")
        if not target_id:
            continue
        ideas = target.get("generated_ideas", [])
        judgments = target.get("judgments", [])
        if len(ideas) != EXPECTED_IDEAS_PER_TARGET:
            add_issue(issues, "fail", "evaluation_idea_count", f"{target_id}: {len(ideas)}")
        if len(judgments) != EXPECTED_IDEAS_PER_TARGET:
            add_issue(issues, "fail", "evaluation_judgment_count", f"{target_id}: {len(judgments)}")

        gen_target = generation_map.get(target_id)
        if gen_target and canonical(ideas) != canonical(gen_target.get("generated_ideas", [])):
            add_issue(issues, "fail", "fixed_ideas_changed", target_id)

        any_match = False
        parse_ok_for_target = 0
        for idx, judgment in enumerate(judgments):
            judgment_count += 1
            parse_status = judgment.get("parse_status", "missing")
            status_counts[parse_status] += 1
            if parse_status == "ok":
                parse_ok_for_target += 1
            else:
                add_issue(issues, "warn", "non_ok_parse_status", f"{target_id} idea {idx}: {parse_status}")

            match_value = judgment.get("match")
            if not isinstance(match_value, bool):
                add_issue(issues, "fail", "non_boolean_match", f"{target_id} idea {idx}: {type(match_value).__name__}")
            if match_value is True:
                any_match = True

        target_parse_ok_counts[target_id] = parse_ok_for_target
        if target.get("hit") is not any_match:
            add_issue(issues, "fail", "target_hit_mismatch", target_id)
        if any_match:
            hit_count += 1

    parse_ok = status_counts.get("ok", 0)
    parse_fail = judgment_count - parse_ok
    parse_rate = round(parse_ok / max(judgment_count, 1) * 100, 1)

    if judgment_count != EXPECTED_JUDGMENTS:
        add_issue(issues, "fail", "total_judgments", f"Expected 770, found {judgment_count}")
    if parse_rate < 95.0:
        add_issue(issues, "fail", "judge_parse_rate", f"Expected >=95.0, found {parse_rate}")
    if evaluation.get("hits") is not None and evaluation.get("hits") != hit_count:
        add_issue(issues, "fail", "reported_hits_mismatch", f"reported={evaluation.get('hits')} recomputed={hit_count}")
    reported_rate = evaluation.get("hit_at_10")
    recomputed_rate = round(hit_count / max(len(targets), 1) * 100, 1)
    if reported_rate is not None and abs(float(reported_rate) - recomputed_rate) > 0.05:
        add_issue(issues, "fail", "reported_hit_rate_mismatch", f"reported={reported_rate} recomputed={recomputed_rate}")

    return {
        "targets": len(targets),
        "unique_targets": len(unique_ids),
        "judgments": judgment_count,
        "parse_ok": parse_ok,
        "parse_fail": parse_fail,
        "parse_rate": parse_rate,
        "status_counts": dict(status_counts),
        "hits": hit_count,
        "hit_at_10": recomputed_rate,
        "judge_total_input_tokens": evaluation.get("judge_total_input_tokens"),
        "judge_total_output_tokens": evaluation.get("judge_total_output_tokens"),
        "judge_total_tokens": evaluation.get("judge_total_tokens"),
        "target_parse_ok_counts": target_parse_ok_counts,
    }


def write_reports(audit: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")

    metrics = audit["metrics"]
    lines = [
        "# Post-Submission GLM-5.1 Self-Judge Audit",
        "",
        f"Generated: {audit['generated']}",
        f"Verdict: **{audit['verdict']}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Targets | {metrics['targets']} |",
        f"| Unique targets | {metrics['unique_targets']} |",
        f"| Judgments | {metrics['judgments']} |",
        f"| Parse OK | {metrics['parse_ok']} |",
        f"| Parse fail | {metrics['parse_fail']} |",
        f"| Parse rate | {metrics['parse_rate']}% |",
        f"| Hits | {metrics['hits']} |",
        f"| Hit@10 | {metrics['hit_at_10']}% |",
        f"| Judge input tokens | {metrics.get('judge_total_input_tokens')} |",
        f"| Judge output tokens | {metrics.get('judge_total_output_tokens')} |",
        f"| Judge total tokens | {metrics.get('judge_total_tokens')} |",
        "",
        "## Files",
        "",
        f"- Generation SHA256: `{audit.get('files', {}).get('generation_sha256', 'missing')}`",
        f"- Evaluation SHA256: `{audit.get('files', {}).get('evaluation_sha256', 'missing')}`",
        "",
        "## Issues",
        "",
    ]
    if audit["issues"]:
        lines.extend(["| Severity | Code | Detail |", "|---|---|---|"])
        for issue in audit["issues"]:
            detail = str(issue["detail"]).replace("|", "\\|")
            lines.append(f"| {issue['severity']} | `{issue['code']}` | {detail} |")
    else:
        lines.append("No issues found.")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def update_manifest(manifest_path: Path, audit: dict, evaluation_path: Path, audit_md_path: Path) -> None:
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    phases = manifest.setdefault("phases", {})
    phase = phases.setdefault("phase_2_clean_zhiyuan_selfjudge", {})
    phase.update(
        {
            "status": "PASS" if audit["verdict"] == "PASS" else "FAIL",
            "script": "scripts/27_evaluate_clean_direct10_zhiyuan.py",
            "audit_script": "scripts/28_audit_clean_direct10_zhiyuan_eval.py",
            "evaluation_file": evaluation_path.name,
            "audit_report": display_path(audit_md_path),
            "judge_model": audit["metadata"].get("judge_model"),
            "targets": audit["metrics"]["targets"],
            "judgments": audit["metrics"]["judgments"],
            "hits": audit["metrics"]["hits"],
            "hit_at_10": audit["metrics"]["hit_at_10"],
            "judge_parse_rate": audit["metrics"]["parse_rate"],
            "paper_rule": "post_submission_diagnostic_only_not_same_metric_as_mimo_main_rows",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit clean Direct-10 GLM-5.1 self-judge evaluation")
    parser.add_argument("--generation", default=str(DEFAULT_GENERATION))
    parser.add_argument("--evaluation", default=str(DEFAULT_EVALUATION))
    parser.add_argument("--audit-json", default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument("--audit-md", default=str(DEFAULT_AUDIT_MD))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--update-manifest", action="store_true")
    args = parser.parse_args()

    generation_path = Path(args.generation)
    evaluation_path = Path(args.evaluation)
    audit_json_path = Path(args.audit_json)
    audit_md_path = Path(args.audit_md)
    manifest_path = Path(args.manifest)

    issues: list[dict] = []
    for path, label in [(generation_path, "generation"), (evaluation_path, "evaluation")]:
        if not path.exists():
            add_issue(issues, "fail", f"missing_{label}_file", str(path))

    if issues:
        audit = {
            "generated": datetime.now().isoformat(),
            "verdict": "FAIL",
            "metadata": {},
            "files": {},
            "metrics": {
                "targets": 0,
                "unique_targets": 0,
                "judgments": 0,
                "parse_ok": 0,
                "parse_fail": 0,
                "parse_rate": 0.0,
                "hits": 0,
                "hit_at_10": 0.0,
            },
            "issues": issues,
        }
        write_reports(audit, audit_json_path, audit_md_path)
        print(f"FAIL: missing required files. Wrote {audit_md_path}")
        return 1

    generation = load_json(generation_path)
    evaluation = load_json(evaluation_path)
    scan_text(evaluation_path, issues)
    generation_map = audit_generation(generation, issues)
    metrics = audit_evaluation(evaluation, generation_map, issues)

    hard_fail = any(issue["severity"] == "fail" for issue in issues)
    verdict = "FAIL" if hard_fail else "PASS"
    audit = {
        "generated": datetime.now().isoformat(),
        "verdict": verdict,
        "metadata": {
            "kind": evaluation.get("kind"),
            "generator_model": evaluation.get("generator_model"),
            "judge_model": evaluation.get("judge_model"),
            "context_mode": evaluation.get("context_mode"),
            "prompt_version": evaluation.get("prompt_version"),
        },
        "files": {
            "generation": display_path(generation_path),
            "generation_sha256": sha256_file(generation_path),
            "evaluation": display_path(evaluation_path),
            "evaluation_sha256": sha256_file(evaluation_path),
        },
        "metrics": metrics,
        "issues": issues,
    }
    write_reports(audit, audit_json_path, audit_md_path)
    if args.update_manifest:
        update_manifest(manifest_path, audit, evaluation_path, audit_md_path)

    print(f"Verdict: {verdict}")
    print(f"Targets: {metrics['targets']}  Judgments: {metrics['judgments']}")
    print(f"Hits: {metrics['hits']}/{metrics['targets']} ({metrics['hit_at_10']}%)")
    print(f"Parse: {metrics['parse_ok']}/{metrics['judgments']} ({metrics['parse_rate']}%)")
    print(f"Audit: {audit_md_path}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
