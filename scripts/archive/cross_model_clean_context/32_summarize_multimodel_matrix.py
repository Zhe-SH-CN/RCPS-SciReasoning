#!/usr/bin/env python3
"""
Summarize post-submission multi-model matrix artifacts.

Local-only script. It scans generation and rejudge JSON files and writes a
compact CSV/Markdown summary without target titles, contributions, raw prompts,
or raw model responses.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXP_DIR = PROJECT_ROOT / "results" / "experiments" / "20260614_multimodel_matrix"
DEFAULT_JSON = PROJECT_ROOT / "results" / "multimodel_matrix_summary_2026-06-14.json"
DEFAULT_CSV = PROJECT_ROOT / "results" / "multimodel_matrix_summary_2026-06-14.csv"
DEFAULT_MD = PROJECT_ROOT / "results" / "multimodel_matrix_summary_2026-06-14.md"

SECRET_PATTERNS = [
    re.compile(r"\b(?:SJTU_API_KEY|XIAOMI_MIMO_API_KEY|OPENAI_API_KEY)\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|authorization|bearer)\b\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,}"),
]
LOCAL_PATH_RE = re.compile(r"(/home/[^\s\"']+|/Users/[^\s\"']+|[A-Za-z]:\\Users\\[^\s\"']+)")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def scan_file(path: Path) -> list[str]:
    text = path.read_text(errors="replace")
    issues = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append("secret_like_pattern")
            break
    if LOCAL_PATH_RE.search(text):
        issues.append("local_absolute_path")
    return issues


def summarize_rejudge(path: Path, obj: dict) -> dict:
    targets = obj.get("targets", [])
    judgments = 0
    status = Counter()
    hits = 0
    for target in targets:
        any_match = False
        for judgment in target.get("judgments", []):
            judgments += 1
            status[judgment.get("parse_status", "missing")] += 1
            if judgment.get("match") is True:
                any_match = True
        if any_match:
            hits += 1
    parse_ok = status.get("ok", 0)
    return {
        "file": display_path(path),
        "kind": obj.get("kind", "rejudge"),
        "source": obj.get("source"),
        "source_model": (obj.get("source_metadata") or {}).get("source_model"),
        "judge_provider": obj.get("judge_provider"),
        "judge_model": obj.get("judge_model"),
        "targets": len(targets),
        "completed": obj.get("completed", len(targets)),
        "ideas_or_judgments": judgments,
        "hits": hits,
        "hit_at_10": round(hits / max(len(targets), 1) * 100, 1),
        "parse_ok": parse_ok,
        "parse_fail": judgments - parse_ok,
        "parse_rate": round(parse_ok / max(judgments, 1) * 100, 1),
        "all_complete": obj.get("all_complete"),
        "tokens": obj.get("judge_total_tokens"),
        "issues": scan_file(path),
    }


def summarize_generation(path: Path, obj: dict) -> dict:
    targets = obj.get("targets", [])
    ideas = sum(len(t.get("generated_ideas", [])) for t in targets)
    parse_ok = sum(1 for t in targets if t.get("generation", {}).get("parse_status") == "ok")
    parse_fail = len(targets) - parse_ok
    return {
        "file": display_path(path),
        "kind": obj.get("kind", "generation"),
        "source": "clean_direct10_generation",
        "source_model": obj.get("generator_model"),
        "judge_provider": "",
        "judge_model": "",
        "targets": len(targets),
        "completed": obj.get("completed", len(targets)),
        "ideas_or_judgments": ideas,
        "hits": "",
        "hit_at_10": "",
        "parse_ok": parse_ok,
        "parse_fail": parse_fail,
        "parse_rate": round(parse_ok / max(len(targets), 1) * 100, 1),
        "all_complete": obj.get("completed") == obj.get("total_targets") and ideas == obj.get("total_targets", 0) * 10,
        "tokens": obj.get("total_tokens") or ((obj.get("total_input_tokens") or 0) + (obj.get("total_output_tokens") or 0)),
        "issues": scan_file(path),
    }


def summarize_path(path: Path) -> dict | None:
    try:
        obj = load_json(path)
    except Exception as exc:
        return {
            "file": display_path(path),
            "kind": "unreadable_json",
            "source": "",
            "source_model": "",
            "judge_provider": "",
            "judge_model": "",
            "targets": 0,
            "completed": 0,
            "ideas_or_judgments": 0,
            "hits": "",
            "hit_at_10": "",
            "parse_ok": 0,
            "parse_fail": 0,
            "parse_rate": 0,
            "all_complete": False,
            "tokens": "",
            "issues": [f"json_error:{exc}"],
        }
    kind = obj.get("kind", "")
    if kind == "rejudge_fixed_final_ideas":
        return summarize_rejudge(path, obj)
    if kind == "generation_direct10_cleanctx":
        return summarize_generation(path, obj)
    return None


def write_outputs(rows: list[dict], json_path: Path, csv_path: Path, md_path: Path) -> None:
    payload = {
        "generated": datetime.now().isoformat(),
        "rows": rows,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    fieldnames = [
        "file",
        "kind",
        "source",
        "source_model",
        "judge_provider",
        "judge_model",
        "targets",
        "completed",
        "ideas_or_judgments",
        "hits",
        "hit_at_10",
        "parse_ok",
        "parse_fail",
        "parse_rate",
        "all_complete",
        "tokens",
        "issues",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["issues"] = ";".join(row.get("issues", []))
            writer.writerow(out)

    lines = [
        "# Multi-Model Matrix Summary",
        "",
        f"Generated: {payload['generated']}",
        "",
        "| Kind | Source | Source model | Judge | Targets | N | Hits | Hit@10 | Parse | Complete | Issues |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        judge = row["judge_model"] if row["judge_model"] else ""
        if row["judge_provider"]:
            judge = f"{row['judge_provider']}/{judge}"
        issues = ", ".join(row.get("issues", [])) if row.get("issues") else ""
        lines.append(
            f"| {row['kind']} | {row['source']} | {row['source_model'] or ''} | {judge} | "
            f"{row['targets']} | {row['ideas_or_judgments']} | {row['hits']} | {row['hit_at_10']} | "
            f"{row['parse_rate']}% | {row['all_complete']} | {issues} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize multimodel matrix artifacts")
    parser.add_argument("--input-dir", default=str(EXP_DIR))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--md", default=str(DEFAULT_MD))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    paths = sorted(input_dir.glob("*.json"))
    rows = []
    for path in paths:
        row = summarize_path(path)
        if row:
            rows.append(row)
    write_outputs(rows, Path(args.json), Path(args.csv), Path(args.md))
    print(f"Summarized {len(rows)} artifacts from {input_dir}")
    print(f"Markdown: {args.md}")
    print(f"CSV: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
