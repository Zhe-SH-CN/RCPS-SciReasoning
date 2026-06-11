#!/usr/bin/env python3
"""
PGCR Phase 3: Select Top-10 candidates with diversity-aware selection.

Deterministic — no MiMo calls. Uses simple text overlap for dedup.
"""

import json
import re
import sys
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def normalize_text(text: str) -> set[str]:
    """Normalize text to word set for overlap comparison."""
    words = re.findall(r'\w+', text.lower())
    return set(words)


def jaccard_overlap(set1: set, set2: set) -> float:
    """Jaccard similarity between two word sets."""
    if not set1 or not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)


def select_top10(candidates: list[dict], overlap_threshold: float = 0.6) -> list[dict]:
    """
    Diversity-aware Top-10 selection:
    1. Sort by overall score descending.
    2. Iteratively add best candidate.
    3. Skip if too similar to already selected (Jaccard > threshold).
    4. Keep pattern diversity when possible.
    """
    # Sort by score
    scored = [(c, c.get("scores", {}).get("overall", 0)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = []
    selected_word_sets = []
    pattern_counts = Counter()

    for cand, score in scored:
        if len(selected) >= 10:
            break

        # Check diversity against already selected
        cand_words = normalize_text(cand.get("idea_title", "") + " " + cand.get("idea_description", ""))
        is_duplicate = False
        for sel_words in selected_word_sets:
            if jaccard_overlap(cand_words, sel_words) > overlap_threshold:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        # Prefer pattern diversity: slight bonus for underrepresented patterns
        pattern = cand.get("pattern_id", "unknown")
        diversity_bonus = 0.01 / (1 + pattern_counts[pattern])

        selected.append(cand)
        selected_word_sets.append(cand_words)
        pattern_counts[pattern] += 1

    return selected


def main():
    parser = argparse.ArgumentParser(description="PGCR Top-10 selection")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "results" / "pgcr_scored.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "pgcr_top10.jsonl"))
    parser.add_argument("--overlap-threshold", type=float, default=0.6)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with open(args.input) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} targets")

    results = []
    total_selected = 0
    total_patterns_used = Counter()

    for record in records:
        candidates = record.get("candidates", [])
        selected = select_top10(candidates, args.overlap_threshold)

        for i, cand in enumerate(selected):
            cand["rank"] = i + 1

        result_obj = {
            "target_id": record["target_id"],
            "target_title": record.get("target_title", ""),
            "total_candidates": len(candidates),
            "selected_count": len(selected),
            "selected": selected,
        }
        results.append(result_obj)
        total_selected += len(selected)

        for cand in selected:
            total_patterns_used[cand.get("pattern_id", "unknown")] += 1

    # Write output
    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n{'='*50}")
    print(f"Top-10 Selection Summary:")
    print(f"  Targets: {len(results)}")
    print(f"  Total selected: {total_selected}")
    print(f"  Avg per target: {round(total_selected / max(len(results), 1), 1)}")
    print(f"  Pattern distribution in selected:")
    for pattern, count in total_patterns_used.most_common():
        print(f"    {pattern}: {count}")
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    sys.exit(main())
