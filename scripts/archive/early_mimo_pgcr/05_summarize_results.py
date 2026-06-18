#!/usr/bin/env python3
"""
Summarize baseline or PGCR results into a markdown report.

Usage:
  python scripts/05_summarize_results.py --input results/baseline_mimo.json --output results/baseline_summary.md
  python scripts/05_summarize_results.py --input results/pgcr_full.json --output results/pgcr_summary.md
"""

import json
import sys
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    targets = data.get("targets", [])
    completed = len(targets)
    hits = sum(1 for t in targets if t.get("hit"))
    hit_rate = round(hits / max(completed, 1) * 100, 1)

    # Token stats
    total_in = sum(
        t.get("generation", {}).get("input_tokens") or 0 for t in targets
    )
    total_out = sum(
        t.get("generation", {}).get("output_tokens") or 0 for t in targets
    )

    # Idea stats
    idea_counts = [len(t.get("generated_ideas", [])) for t in targets]
    avg_ideas = round(sum(idea_counts) / max(len(idea_counts), 1), 1) if idea_counts else 0

    # Judgment confidence
    confidences = []
    for t in targets:
        for j in t.get("judgments", []):
            if "confidence" in j:
                confidences.append(j["confidence"])
    avg_conf = round(sum(confidences) / max(len(confidences), 1), 2) if confidences else 0

    # Failure analysis
    failures = data.get("failures", [])

    # Miss cases (for method design)
    miss_cases = [t for t in targets if not t.get("hit")]
    hit_cases = [t for t in targets if t.get("hit")]

    lines = []
    lines.append(f"# Results Summary")
    lines.append(f"")
    lines.append(f"Generated: {data.get('run_id', 'unknown')}")
    lines.append(f"Model: {data.get('model', 'unknown')}")
    lines.append(f"")
    lines.append(f"## Overview")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total targets | {data.get('total_targets', completed)} |")
    lines.append(f"| Completed | {completed} |")
    lines.append(f"| Hits | {hits} |")
    lines.append(f"| **Hit@10** | **{hit_rate}%** |")
    lines.append(f"| Failed | {len(failures)} |")
    lines.append(f"| Avg ideas/target | {avg_ideas} |")
    lines.append(f"| Avg judge confidence | {avg_conf} |")
    lines.append(f"| Total input tokens | {total_in:,} |")
    lines.append(f"| Total output tokens | {total_out:,} |")
    lines.append(f"")

    # Hit cases
    if hit_cases:
        lines.append(f"## Hit Cases ({len(hit_cases)})")
        lines.append(f"")
        for t in hit_cases[:10]:
            lines.append(f"- **{t.get('target_title', '')[:80]}**")
            matched = [j for j in t.get("judgments", []) if j.get("match")]
            for m in matched[:2]:
                idx = m.get("idea_index", 0)
                ideas = t.get("generated_ideas", [])
                if idx < len(ideas):
                    lines.append(f"  - Matched idea: {ideas[idx].get('idea_title', '')[:60]}")
        lines.append(f"")

    # Miss cases
    if miss_cases:
        lines.append(f"## Miss Cases ({len(miss_cases)})")
        lines.append(f"")
        for t in miss_cases[:10]:
            lines.append(f"- {t.get('target_title', '')[:80]}")
        lines.append(f"")

    # Failures
    if failures:
        lines.append(f"## Failures ({len(failures)})")
        lines.append(f"")
        for fail in failures[:10]:
            lines.append(f"- {fail.get('title', '')[:60]}: {fail.get('error', '')[:100]}")
        lines.append(f"")

    report = "\n".join(lines)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)
    print(f"Summary written to {args.output}")
    print(f"Hit@10: {hit_rate}% ({hits}/{completed})")


if __name__ == "__main__":
    sys.exit(main())
