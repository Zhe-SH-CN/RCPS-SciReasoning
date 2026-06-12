#!/usr/bin/env python3
"""Enrich eval_neurips_2025_oral.jsonl with contribution fields from Sci-Reasoning result files.

Creates:
  - data/scireasoning/eval_neurips_2025_oral_enriched.jsonl
  - data/scireasoning/enrichment_report.md
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"
ENRICHED_PATH = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
REPORT_PATH = PROJECT_ROOT / "data" / "scireasoning" / "enrichment_report.md"

# Source files in priority order (per CLAUDE.md ground truth priority)
SOURCE_FILES = [
    "Sci-Reasoning/research_idea_evaluation/results/evaluation_results_claude_sonnet_final.json",
    "Sci-Reasoning/research_idea_evaluation/results/evaluation_results_claude_opus_final.json",
    "Sci-Reasoning/research_idea_evaluation/results/evaluation_results_gemini_25pro_final.json",
    "Sci-Reasoning/research_idea_evaluation/results/evaluation_results_gpt52_v3_exa_final.json",
]


def normalize_title(title: str) -> str:
    """Normalize title for matching: lowercase, collapse whitespace, strip."""
    t = title.lower().strip()
    t = re.sub(r'\s+', ' ', t)
    return t


def load_contributions_from_source(source_path: Path) -> dict[str, dict]:
    """Load paper_title -> {contribution, source} mapping from a source file."""
    with open(source_path) as f:
        data = json.load(f)
    results = data.get("results", [])
    mapping = {}
    for r in results:
        title = r.get("paper_title", "")
        contrib = r.get("contribution", "")
        if title and contrib:
            norm = normalize_title(title)
            mapping[norm] = {
                "contribution": contrib,
                "source": source_path.name,
            }
    return mapping


def strip_private_paths(text: str) -> str:
    """Remove /home/... and /Users/... paths from text."""
    text = re.sub(r'/home/\S+', '[path-removed]', text)
    text = re.sub(r'/Users/\S+', '[path-removed]', text)
    return text


def main():
    # Load eval records
    records = []
    with open(EVAL_PATH) as f:
        for line in f:
            records.append(json.loads(line))
    print(f"Loaded {len(records)} eval records")

    # Build contribution lookup from all sources
    all_contributions: dict[str, dict] = {}
    source_counts = {}
    for src in SOURCE_FILES:
        src_path = PROJECT_ROOT / src
        if not src_path.exists():
            print(f"  Warning: source not found: {src}")
            continue
        mapping = load_contributions_from_source(src_path)
        print(f"  {src}: {len(mapping)} contributions")
        for norm_title, info in mapping.items():
            if norm_title not in all_contributions:
                all_contributions[norm_title] = info
                source_counts[info["source"]] = source_counts.get(info["source"], 0) + 1

    print(f"Total unique contributions: {len(all_contributions)}")

    # Match and enrich
    enriched = []
    matched = 0
    unmatched = []
    for rec in records:
        norm = normalize_title(rec["title"])
        if norm in all_contributions:
            rec["contribution"] = all_contributions[norm]["contribution"]
            rec["contribution_source"] = all_contributions[norm]["source"]
            matched += 1
        else:
            # Try fuzzy match: check if any source title is a substring
            found = False
            for src_norm, info in all_contributions.items():
                if norm in src_norm or src_norm in norm:
                    rec["contribution"] = info["contribution"]
                    rec["contribution_source"] = info["source"] + " (fuzzy)"
                    matched += 1
                    found = True
                    break
            if not found:
                unmatched.append(rec["title"])
                rec["contribution"] = ""
                rec["contribution_source"] = ""
        # Strip private paths from all text fields
        for key in ["contribution", "abstract", "synthesis_narrative"]:
            if rec.get(key):
                rec[key] = strip_private_paths(rec[key])
        if rec.get("source_path"):
            rec["source_path"] = strip_private_paths(rec["source_path"])
        enriched.append(rec)

    print(f"Matched: {matched}/{len(records)}")
    print(f"Unmatched: {len(unmatched)}")

    # Write enriched JSONL
    with open(ENRICHED_PATH, "w") as f:
        for rec in enriched:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote: {ENRICHED_PATH}")

    # Write enrichment report
    with open(REPORT_PATH, "w") as f:
        f.write("# Enrichment Report\n\n")
        f.write(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Input: `{EVAL_PATH.name}` ({len(records)} records)\n")
        f.write(f"- Output: `{ENRICHED_PATH.name}` ({len(enriched)} records)\n")
        f.write(f"- Matched: {matched}/{len(records)}\n")
        f.write(f"- Unmatched: {len(unmatched)}\n\n")

        f.write("## Source Priority\n\n")
        f.write("Sources tried in order (per CLAUDE.md ground truth priority):\n\n")
        for i, src in enumerate(SOURCE_FILES, 1):
            src_path = PROJECT_ROOT / src
            status = "found" if src_path.exists() else "missing"
            cnt = source_counts.get(Path(src).name, 0)
            f.write(f"{i}. `{src}` — {status}, {cnt} contributions used\n")
        f.write("\n")

        f.write("## Matched Records\n\n")
        f.write("| # | Title | Source |\n|---|---|---|\n")
        for i, rec in enumerate(enriched, 1):
            if rec.get("contribution"):
                title_short = rec["title"][:60]
                f.write(f"| {i} | {title_short} | {rec.get('contribution_source', '')} |\n")
        f.write("\n")

        if unmatched:
            f.write("## Unmatched Records\n\n")
            f.write("These records could not be matched to any source contribution:\n\n")
            for title in unmatched:
                f.write(f"- {title}\n")
            f.write("\n")

        f.write("## Validation\n\n")
        non_empty = sum(1 for r in enriched if r.get("contribution"))
        f.write(f"- Non-empty contributions: {non_empty}/{len(enriched)}\n")
        has_source = sum(1 for r in enriched if r.get("contribution_source"))
        f.write(f"- Has contribution_source: {has_source}/{len(enriched)}\n")
        # Check for private paths
        path_issues = []
        for rec in enriched:
            for key in ["contribution", "abstract", "synthesis_narrative"]:
                val = rec.get(key, "")
                if "/home/" in val or "/Users/" in val:
                    path_issues.append(f"{rec['title']}.{key}")
        f.write(f"- Private path issues: {len(path_issues)}\n")
        # Check predecessor counts
        pred_counts = [len(r.get("predecessors", [])) for r in enriched]
        avg_preds = sum(pred_counts) / len(pred_counts) if pred_counts else 0
        f.write(f"- Average predecessors: {avg_preds:.1f}\n")
        f.write("\n")

        if path_issues:
            f.write("## Path Issues\n\n")
            for issue in path_issues:
                f.write(f"- {issue}\n")
            f.write("\n")

    print(f"Wrote: {REPORT_PATH}")

    # Final validation
    non_empty = sum(1 for r in enriched if r.get("contribution"))
    assert non_empty == 77, f"Expected 77 non-empty contributions, got {non_empty}"
    print(f"Validation passed: {non_empty}/77 non-empty contributions")


if __name__ == "__main__":
    main()
