#!/usr/bin/env python3
"""
Build a sanitized post-submission GLM-5.1 robustness packet.

This script reads the audited clean-context GLM-5.1 self-judge result and
produces paper-facing summaries without target titles, target contributions,
raw prompts, raw judge responses, or API metadata.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "results" / "experiments" / "20260614_cross_model_zhiyuan1"

DEFAULT_AUDIT = PROJECT_ROOT / "results" / "post_submission_glm51_selfjudge_audit_2026-06-14.json"
DEFAULT_EVALUATION = EXP_DIR / "evaluation_direct10_glm-51_glm-51_selfjudge_cleanctx_77t_20260614.json"
DEFAULT_MAIN_AUDIT = PROJECT_ROOT / "results" / "acml_results_audit.json"
DEFAULT_MD = PROJECT_ROOT / "results" / "post_submission_glm51_robustness_packet_2026-06-14.md"
DEFAULT_CSV = PROJECT_ROOT / "results" / "post_submission_glm51_target_outcomes_2026-06-14.csv"


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def main_result_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    obj = load_json(path)
    methods = obj.get("methods", {})
    rows = []
    for label, key in [
        ("Direct-10", "baseline_enriched"),
        ("BCS-50", "bcs50"),
        ("PGCR", "pgcr_enriched"),
    ]:
        rec = methods.get(key)
        if not rec:
            continue
        rows.append(
            {
                "method": label,
                "judge": "MiMo v2.5-pro enriched contribution",
                "hits": rec.get("hits"),
                "targets": rec.get("total_targets", 77),
                "hit_at_10": rec.get("hit_at_10"),
                "ci": rec.get("bootstrap_95ci", {}),
            }
        )
    return rows


def write_outcomes_csv(evaluation: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "target_id",
                "hit",
                "match_count",
                "parse_ok_count",
                "parse_fail_count",
                "max_confidence",
            ],
        )
        writer.writeheader()
        for target in evaluation.get("targets", []):
            judgments = target.get("judgments", [])
            match_count = sum(1 for j in judgments if j.get("match") is True)
            parse_ok_count = sum(1 for j in judgments if j.get("parse_status") == "ok")
            confidences = [
                float(j.get("confidence", 0.0) or 0.0)
                for j in judgments
                if isinstance(j.get("confidence", 0.0), (int, float))
            ]
            writer.writerow(
                {
                    "target_id": target.get("target_id"),
                    "hit": bool(target.get("hit")),
                    "match_count": match_count,
                    "parse_ok_count": parse_ok_count,
                    "parse_fail_count": len(judgments) - parse_ok_count,
                    "max_confidence": round(max(confidences) if confidences else 0.0, 3),
                }
            )


def build_markdown(audit: dict, main_rows: list[dict], output_csv: Path) -> str:
    metrics = audit.get("metrics", {})
    verdict = audit.get("verdict")
    judge_model = audit.get("metadata", {}).get("judge_model")
    generator_model = audit.get("metadata", {}).get("generator_model")
    generation_hash = audit.get("files", {}).get("generation_sha256")
    evaluation_hash = audit.get("files", {}).get("evaluation_sha256")

    lines = [
        "# Post-Submission GLM-5.1 Robustness Packet",
        "",
        "This packet is for ACML #71 rebuttal or camera-ready use only. It is not part of the submitted main paper unless explicitly revised later.",
        "",
        "## Decision",
        "",
        f"- Audit verdict: **{verdict}**.",
        f"- Generator: `{generator_model}`.",
        f"- Judge: `{judge_model}` self-judge.",
        "- Protocol: clean-context Direct-10 generation from predecessor titles only; target title/contribution visible only during final judging.",
        "- Interpretation rule: diagnostic second-model evidence only. Do not compare this number as the same metric against MiMo-judge main rows.",
        "",
        "## GLM-5.1 Diagnostic Result",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Targets | {metrics.get('targets')} |",
        f"| Judgments | {metrics.get('judgments')} |",
        f"| Parse OK | {metrics.get('parse_ok')} |",
        f"| Parse fail | {metrics.get('parse_fail')} |",
        f"| Parse rate | {metrics.get('parse_rate')}% |",
        f"| Hits | {metrics.get('hits')}/{metrics.get('targets')} |",
        f"| Hit@10 | {metrics.get('hit_at_10')}% |",
        f"| Judge input tokens | {metrics.get('judge_total_input_tokens')} |",
        f"| Judge output tokens | {metrics.get('judge_total_output_tokens')} |",
        f"| Judge total tokens | {metrics.get('judge_total_tokens')} |",
        "",
        "## Submitted Main Rows For Context",
        "",
        "These are the submitted-paper MiMo enriched-judge rows. They are shown only to keep the post-submission result in context.",
        "",
    ]

    if main_rows:
        lines.extend(["| Method | Judge | Hits | Hit@10 | 95% CI |", "|---|---|---:|---:|---|"])
        for row in main_rows:
            ci = row.get("ci") or {}
            ci_text = ""
            if ci:
                ci_text = f"[{ci.get('low')}, {ci.get('high')}]"
            lines.append(
                f"| {row['method']} | {row['judge']} | {row.get('hits')}/{row.get('targets')} | {row.get('hit_at_10')}% | {ci_text} |"
            )
    else:
        lines.append("Main-result audit file was not available.")

    lines.extend(
        [
            "",
            "## Safe Use In Rebuttal",
            "",
            "A safe sentence, if the result is useful:",
            "",
            "> After submission, we also ran a clean-context Direct-10 diagnostic with GLM-5.1 as both generator and judge. The run completed 77 targets and 770 judgments with the audit-reported parse rate; because the judge differs from the submitted MiMo enriched judge, we treat it as robustness evidence about protocol/model sensitivity rather than as a replacement main result.",
            "",
            "Do not say:",
            "",
            "- GLM-5.1 improves over Direct-10 unless all compared methods are evaluated under the same judge.",
            "- The submitted main table has changed.",
            "- The diagnostic result is SOTA or a leaderboard score.",
            "",
            "## Sanitized Artifacts",
            "",
            f"- Target-outcome CSV: `{display_path(output_csv)}`.",
            f"- Generation SHA256: `{generation_hash}`.",
            f"- Evaluation SHA256: `{evaluation_hash}`.",
            "",
            "The CSV intentionally contains target IDs and aggregate labels only. It excludes target titles, contributions, prompts, raw model responses, and local paths.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sanitized GLM-5.1 post-submission robustness packet")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--evaluation", default=str(DEFAULT_EVALUATION))
    parser.add_argument("--main-audit", default=str(DEFAULT_MAIN_AUDIT))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    parser.add_argument("--output-csv", default=str(DEFAULT_CSV))
    parser.add_argument("--allow-fail-audit", action="store_true")
    args = parser.parse_args()

    audit_path = Path(args.audit)
    evaluation_path = Path(args.evaluation)
    output_md = Path(args.output_md)
    output_csv = Path(args.output_csv)

    if not audit_path.exists():
        print(f"Missing audit file: {audit_path}", file=sys.stderr)
        return 1
    if not evaluation_path.exists():
        print(f"Missing evaluation file: {evaluation_path}", file=sys.stderr)
        return 1

    audit = load_json(audit_path)
    if audit.get("verdict") != "PASS" and not args.allow_fail_audit:
        print(f"Audit verdict is {audit.get('verdict')}; refusing to build packet without --allow-fail-audit", file=sys.stderr)
        return 1

    evaluation = load_json(evaluation_path)
    write_outcomes_csv(evaluation, output_csv)
    md = build_markdown(audit, main_result_rows(Path(args.main_audit)), output_csv)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(md, encoding="utf-8")

    print(f"Wrote {output_md}")
    print(f"Wrote {output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
