#!/usr/bin/env python3
"""
Phase 1 Task 1: Enrich eval_neurips_2025_oral.jsonl with contributions.

Reads contribution text from Sci-Reasoning evaluation result files,
matches by normalized title, and produces:
  - data/scireasoning/eval_neurips_2025_oral_enriched.jsonl
  - data/scireasoning/enrichment_report.md

Rules:
  - Preserve all 77 target records.
  - Fill every contribution field.
  - Add contribution_source.
  - Match by normalized title (lowercase, stripped).
  - Prefer longest available contribution per title.
  - Remove /home/ paths from paper-facing fields.
"""

import json
import glob
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_JSONL = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"
SR_RESULTS_DIR = PROJECT_ROOT / "Sci-Reasoning" / "research_idea_evaluation" / "results"
OUTPUT_JSONL = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "scireasoning" / "enrichment_report.md"


def normalize_title(title: str) -> str:
    return title.lower().strip()


def load_best_contributions() -> dict[str, dict]:
    """Load the longest contribution per title from all *_final.json files."""
    best: dict[str, dict] = {}
    for path in sorted(SR_RESULTS_DIR.glob("*_final.json")):
        with open(path) as f:
            data = json.load(f)
        for r in data.get("results", []):
            title = r.get("paper_title", "").strip()
            contrib = r.get("contribution", "").strip()
            if not title:
                continue
            key = normalize_title(title)
            if key not in best or len(contrib) > len(best[key]["contribution"]):
                best[key] = {
                    "contribution": contrib,
                    "source_file": path.name,
                }
    return best


def clean_source_path(path: str) -> str:
    """Remove /home/ and /Users/ paths from source_path."""
    if not path:
        return path
    # Replace full local paths with just the filename
    path = re.sub(r"/home/[^/]+/\S+", "", path)
    path = re.sub(r"/Users/[^/]+/\S+", "", path)
    return path.strip()


def main():
    contributions = load_best_contributions()
    print(f"Loaded {len(contributions)} contributions from Sci-Reasoning results.")

    # Load eval JSONL
    records = []
    with open(EVAL_JSONL) as f:
        for line in f:
            records.append(json.loads(line))

    print(f"Loaded {len(records)} eval records.")

    # Enrich
    enriched = []
    matched = 0
    unmatched = []
    for rec in records:
        key = normalize_title(rec["title"])
        if key in contributions:
            rec["contribution"] = contributions[key]["contribution"]
            rec["contribution_source"] = contributions[key]["source_file"]
            matched += 1
        else:
            rec["contribution_source"] = "missing"
            unmatched.append(rec["title"])

        # Clean source_path
        if "source_path" in rec:
            rec["source_path"] = clean_source_path(rec["source_path"])

        enriched.append(rec)

    # Write enriched JSONL
    with open(OUTPUT_JSONL, "w") as f:
        for rec in enriched:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Verify
    non_empty = sum(1 for r in enriched if r.get("contribution", "").strip())
    has_path_leak = any(
        re.search(r"/home/|/Users/", r.get("contribution", ""))
        for r in enriched
    )

    # Compute predecessor stats
    pred_counts = [len(r.get("predecessors", [])) for r in enriched]
    avg_preds = sum(pred_counts) / len(pred_counts) if pred_counts else 0

    # Write report
    report_lines = [
        "# Enrichment Report",
        "",
        f"Generated from: `data/scireasoning/eval_neurips_2025_oral.jsonl`",
        f"Contributions sourced from: `Sci-Reasoning/research_idea_evaluation/results/*_final.json`",
        "",
        "## Summary",
        "",
        f"- Total records: {len(enriched)}",
        f"- Matched contributions: {matched}",
        f"- Non-empty contributions: {non_empty}",
        f"- Empty contributions: {len(enriched) - non_empty}",
        f"- Average predecessor count: {avg_preds:.1f}",
        f"- Path leaks in contributions: {'YES' if has_path_leak else 'No'}",
        "",
    ]

    if unmatched:
        report_lines.append("## Unmatched Titles")
        report_lines.append("")
        for t in unmatched:
            report_lines.append(f"- {t}")
        report_lines.append("")

    # Contribution source distribution
    from collections import Counter
    sources = Counter(r.get("contribution_source", "missing") for r in enriched)
    report_lines.append("## Contribution Sources")
    report_lines.append("")
    for src, cnt in sources.most_common():
        report_lines.append(f"- `{src}`: {cnt}")
    report_lines.append("")

    # Validation
    report_lines.append("## Validation")
    report_lines.append("")
    report_lines.append(f"- [x] 77 records preserved" if len(enriched) == 77 else f"- [ ] Expected 77 records, got {len(enriched)}")
    report_lines.append(f"- [x] 77 non-empty contributions" if non_empty == 77 else f"- [ ] Expected 77 non-empty, got {non_empty}")
    report_lines.append(f"- [x] No path leaks" if not has_path_leak else "- [ ] Path leaks detected")
    report_lines.append("")

    with open(OUTPUT_REPORT, "w") as f:
        f.write("\n".join(report_lines))

    print(f"\nEnrichment complete:")
    print(f"  Matched: {matched}/{len(enriched)}")
    print(f"  Non-empty contributions: {non_empty}")
    print(f"  Output: {OUTPUT_JSONL}")
    print(f"  Report: {OUTPUT_REPORT}")

    if unmatched:
        print(f"\n  WARNING: {len(unmatched)} unmatched titles")


if __name__ == "__main__":
    main()
