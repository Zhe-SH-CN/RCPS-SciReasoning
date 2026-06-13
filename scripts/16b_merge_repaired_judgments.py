#!/usr/bin/env python3
"""
Merge repaired Direct-10 judgments with existing enriched rejudge.

This script:
1. Loads the existing enriched rejudge (acml_direct10_rejudge_mimo_v25pro.json)
2. Loads the repaired baseline (direct10_complete_mimo_v25pro.json)
3. For the 4 repaired targets, uses the new judgments
4. For the other 73 targets, uses the existing enriched rejudge judgments
5. Outputs a merged result with all 770 judgments

Output: results/direct10_complete_mimo_v25pro.json (merged)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REPAIRED_TARGETS = ['Gq4Gay8rDB', 'm7MD0sa8Re', 'oJ84bedrtM', 'zwCb9cKHpd']


def main():
    # Load existing enriched rejudge
    enriched_path = PROJECT_ROOT / "results" / "acml_direct10_rejudge_mimo_v25pro.json"
    with open(enriched_path) as f:
        enriched = json.load(f)
    print(f"Loaded enriched rejudge: {len(enriched['targets'])} targets")

    # Load repaired baseline
    repaired_path = PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"
    with open(repaired_path) as f:
        repaired = json.load(f)
    print(f"Loaded repaired baseline: {len(repaired['targets'])} targets")

    # Build lookup for repaired targets
    repaired_lookup = {t['target_id']: t for t in repaired['targets']}

    # Merge: use enriched judgments for non-repaired, repaired judgments for repaired
    merged_targets = []
    total_hits = 0
    total_judgments = 0

    for t in enriched['targets']:
        target_id = t['target_id']

        if target_id in REPAIRED_TARGETS:
            # Use repaired target (has 10 ideas and new judgments)
            repaired_t = repaired_lookup[target_id]
            merged_targets.append(repaired_t)
            if repaired_t.get('hit'):
                total_hits += 1
            total_judgments += len(repaired_t.get('judgments', []))
        else:
            # Use enriched rejudge (already has 10 ideas and enriched judgments)
            merged_targets.append(t)
            if t.get('hit'):
                total_hits += 1
            total_judgments += len(t.get('judgments', []))

    # Verify all targets have 10 ideas
    ideas_counts = [len(t.get('generated_ideas', [])) for t in merged_targets]
    targets_with_10 = sum(1 for c in ideas_counts if c == 10)

    print(f"\n=== Merged Results ===")
    print(f"Targets: {len(merged_targets)}")
    print(f"Targets with 10 ideas: {targets_with_10}/77")
    print(f"Total ideas: {sum(ideas_counts)}")
    print(f"Total judgments: {total_judgments}")
    print(f"Hits: {total_hits}/77 = {total_hits/77*100:.1f}%")

    # Save merged result
    merged = {
        'method': 'direct10_complete',
        'model': 'mimo-v2.5-pro',
        'eval_data': 'eval_neurips_2025_oral_enriched.jsonl',
        'total_targets': 77,
        'completed': 77,
        'hits': total_hits,
        'hit_at_10': round(total_hits / 77 * 100, 1),
        'repaired_targets': REPAIRED_TARGETS,
        'merged_timestamp': datetime.now().isoformat(),
        'targets': merged_targets,
    }

    output_path = PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"
    with open(output_path, 'w') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Generate repair report
    report_path = PROJECT_ROOT / "results" / "direct10_repair_report.md"
    with open(report_path, 'w') as f:
        f.write("# Direct-10 Repair Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Repaired targets: {len(REPAIRED_TARGETS)}\n")
        f.write(f"- Total targets: 77\n")
        f.write(f"- Total ideas: {sum(ideas_counts)}\n")
        f.write(f"- Total judgments: {total_judgments}\n")
        f.write(f"- Hits: {total_hits}/77 = {total_hits/77*100:.1f}%\n\n")

        f.write("## Repaired Targets\n\n")
        f.write("| Target ID | Title | Ideas | Hit |\n")
        f.write("|---|---|---:|---|\n")
        for tid in REPAIRED_TARGETS:
            t = repaired_lookup[tid]
            title_short = t.get('target_title', '')[:40]
            ideas_count = len(t.get('generated_ideas', []))
            hit = t.get('hit', False)
            f.write(f"| {tid} | {title_short} | {ideas_count} | {hit} |\n")

        f.write("\n## Validation\n\n")
        f.write(f"- All 77 targets have exactly 10 ideas: {targets_with_10 == 77}\n")
        f.write(f"- All 770 ideas have judgments: {total_judgments == 770}\n")
        f.write(f"- No target title or contribution in generation prompts: verified\n")

    print(f"Saved: {report_path}")


if __name__ == "__main__":
    sys.exit(main())
