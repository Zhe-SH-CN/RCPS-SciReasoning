#!/usr/bin/env python3
"""
Prepare Sci-Reasoning data for ICTAI experiments.

Joins three local data sources:
1. ml_paper_acquisition/results/data/2025/oral_spotlight_papers_2025.json
   (paper metadata: title, authors, abstract, openreview_id)
2. prior_work_extraction/results/organized/NeurIPS_2025/{id}.json
   (predecessors: prior_works, synthesis_narrative)
3. thinking_patterns_llm_analysis/results/classified_papers.json
   (innovation patterns: primary_pattern, secondary_patterns)

Outputs:
- data/scireasoning/manifest.json
- data/scireasoning/eval_neurips_2025_oral.jsonl
- data/scireasoning/debug_sample_3.jsonl
"""

import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCI_REASONING = PROJECT_ROOT / "Sci-Reasoning"
OUTPUT_DIR = PROJECT_ROOT / "data" / "scireasoning"

# Source paths
PAPERS_PATH = (
    SCI_REASONING
    / "ml_paper_acquisition"
    / "results"
    / "data"
    / "2025"
    / "oral_spotlight_papers_2025.json"
)
PRIOR_WORK_DIR = (
    SCI_REASONING / "prior_work_extraction" / "results" / "organized" / "NeurIPS_2025"
)
CLASSIFIED_PATH = (
    SCI_REASONING
    / "thinking_patterns_llm_analysis"
    / "results"
    / "classified_papers.json"
)

# Pattern ID to name mapping (from pattern_taxonomy.json)
PATTERN_NAMES = {
    "P01": "Gap-Driven Reframing",
    "P02": "Cross-Domain Synthesis",
    "P03": "Representation Shift",
    "P04": "Data & Evaluation Engineering",
    "P05": "Formal-Experimental Tightening",
    "P06": "Scalability & Efficiency",
    "P07": "Robustness & Failure Mode Analysis",
    "P08": "Composition & Modular Design",
    "P09": "Theoretical Grounding",
    "P10": "Human-AI Collaboration",
    "P11": "Multi-Modal Integration",
    "P12": "Causal & Mechanistic Understanding",
    "P13": "Benchmark & Task Redesign",
    "P14": "Optimization & Training Dynamics",
    "P15": "Alignment & Safety",
}


def load_pattern_taxonomy():
    """Load pattern ID to name mapping from taxonomy file."""
    taxonomy_path = (
        SCI_REASONING
        / "thinking_patterns_llm_analysis"
        / "results"
        / "pattern_taxonomy.json"
    )
    if taxonomy_path.exists():
        with open(taxonomy_path) as f:
            data = json.load(f)
        return {t["id"]: t["name"] for t in data.get("taxonomy", [])}
    return PATTERN_NAMES


def load_paper_metadata():
    """Load paper metadata from ml_paper_acquisition."""
    with open(PAPERS_PATH) as f:
        papers = json.load(f)
    # Index by openreview_id
    by_id = {}
    for p in papers:
        oid = p.get("openreview_id", "")
        if oid:
            by_id[oid] = p
    return by_id


def load_prior_works():
    """Load prior work extraction results from organized directory."""
    prior_dir = PRIOR_WORK_DIR
    results = {}
    for json_file in sorted(prior_dir.glob("*.json")):
        paper_id = json_file.stem
        with open(json_file) as f:
            data = json.load(f)
        results[paper_id] = data
    return results


def load_classified_patterns():
    """Load classified innovation patterns."""
    with open(CLASSIFIED_PATH) as f:
        papers = json.load(f)
    # Index by title (normalized)
    by_title = {}
    for p in papers:
        title = p.get("title", "").strip()
        if title:
            by_title[title] = p
    return by_title


def build_target_record(meta, prior_data, pattern_data, pattern_map):
    """Build a normalized target record from all three sources."""
    openreview_id = meta.get("openreview_id", "")

    # Extract predecessors from prior work data
    predecessors = []
    for pw in prior_data.get("prior_works", []):
        predecessors.append(
            {
                "title": pw.get("title", ""),
                "role": pw.get("role", ""),
                "relationship_sentence": pw.get("relationship_sentence", ""),
                "synthesis_narrative": prior_data.get("synthesis_narrative", ""),
            }
        )

    # Extract patterns
    classification = pattern_data.get("classification", {})
    primary_id = classification.get("primary_pattern", "")
    secondary_ids = classification.get("secondary_patterns", [])
    primary_pattern = pattern_map.get(primary_id, primary_id)
    secondary_patterns = [pattern_map.get(pid, pid) for pid in secondary_ids]

    return {
        "target_id": openreview_id,
        "title": meta.get("title", ""),
        "venue": meta.get("conference", "NeurIPS"),
        "year": meta.get("year", 2025),
        "presentation_type": meta.get("presentation_type", "oral"),
        "abstract": meta.get("abstract", ""),
        "contribution": "",  # Not available in local data
        "predecessors": predecessors,
        "synthesis_narrative": prior_data.get("synthesis_narrative", ""),
        "primary_pattern": primary_pattern,
        "secondary_patterns": secondary_patterns,
        "pattern_confidence": classification.get("confidence", ""),
        "pattern_reasoning": classification.get("reasoning", ""),
        "source_path": str(
            PRIOR_WORK_DIR / f"{openreview_id}.json"
        ),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data sources...")
    pattern_map = load_pattern_taxonomy()
    print(f"  Pattern taxonomy: {len(pattern_map)} patterns")

    meta_by_id = load_paper_metadata()
    print(f"  Paper metadata: {len(meta_by_id)} papers")

    prior_works = load_prior_works()
    print(f"  Prior work files: {len(prior_works)} papers")

    patterns_by_title = load_classified_patterns()
    print(f"  Classified patterns: {len(patterns_by_title)} papers")

    # Filter to NeurIPS 2025 Oral
    neurips_2025_oral = {
        oid: m
        for oid, m in meta_by_id.items()
        if m.get("conference") == "NeurIPS"
        and m.get("year") == 2025
        and m.get("presentation_type") == "oral"
    }
    print(f"\nNeurIPS 2025 Oral targets: {len(neurips_2025_oral)}")

    # Build records
    records = []
    missing_prior = 0
    missing_pattern = 0
    for oid, meta in sorted(neurips_2025_oral.items()):
        prior_data = prior_works.get(oid, {})
        if not prior_data:
            missing_prior += 1

        title = meta.get("title", "").strip()
        pattern_data = patterns_by_title.get(title, {})
        if not pattern_data:
            missing_pattern += 1

        record = build_target_record(meta, prior_data, pattern_data, pattern_map)
        records.append(record)

    print(f"  Missing prior work data: {missing_prior}")
    print(f"  Missing pattern data: {missing_pattern}")

    # Write eval JSONL
    eval_path = OUTPUT_DIR / "eval_neurips_2025_oral.jsonl"
    with open(eval_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(records)} records to {eval_path}")

    # Write debug sample (first 3)
    debug_path = OUTPUT_DIR / "debug_sample_3.jsonl"
    with open(debug_path, "w") as f:
        for rec in records[:3]:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote debug sample to {debug_path}")

    # Write manifest
    manifest = {
        "created": datetime.now().isoformat(),
        "description": "ICTAI Sci-Reasoning data manifest",
        "eval_set": "NeurIPS 2025 Oral",
        "eval_count": len(records),
        "sources": {
            "paper_metadata": str(PAPERS_PATH),
            "prior_works": str(PRIOR_WORK_DIR),
            "classified_patterns": str(CLASSIFIED_PATH),
        },
        "outputs": {
            "eval_jsonl": str(eval_path),
            "debug_sample": str(debug_path),
        },
        "schema": {
            "target_id": "OpenReview forum ID",
            "title": "Paper title",
            "venue": "Conference name",
            "year": "Publication year",
            "presentation_type": "oral or spotlight",
            "abstract": "Paper abstract (may be empty)",
            "contribution": "Paper contribution (not available locally)",
            "predecessors": [
                {
                    "title": "Predecessor paper title",
                    "role": "Relationship role",
                    "relationship_sentence": "How predecessor relates to target",
                    "synthesis_narrative": "How all predecessors combine",
                }
            ],
            "synthesis_narrative": "Narrative connecting predecessors to target",
            "primary_pattern": "Main innovation pattern name",
            "secondary_patterns": "List of secondary pattern names",
            "pattern_confidence": "high/medium/low",
            "pattern_reasoning": "Why this pattern was assigned",
            "source_path": "Path to source prior work JSON",
        },
        "pattern_distribution": {},
        "predecessor_stats": {
            "total": sum(len(r["predecessors"]) for r in records),
            "avg_per_target": round(
                sum(len(r["predecessors"]) for r in records) / max(len(records), 1), 1
            ),
            "min": min(len(r["predecessors"]) for r in records) if records else 0,
            "max": max(len(r["predecessors"]) for r in records) if records else 0,
        },
    }

    # Pattern distribution
    from collections import Counter

    pattern_counts = Counter()
    for rec in records:
        pp = rec.get("primary_pattern", "Unknown")
        pattern_counts[pp] += 1
    manifest["pattern_distribution"] = dict(pattern_counts.most_common())

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote manifest to {manifest_path}")

    # Summary
    print(f"\n{'='*50}")
    print("Summary:")
    print(f"  Eval targets: {len(records)}")
    print(f"  Total predecessors: {manifest['predecessor_stats']['total']}")
    print(f"  Avg predecessors/target: {manifest['predecessor_stats']['avg_per_target']}")
    print(f"  Pattern distribution:")
    for pattern, count in pattern_counts.most_common():
        print(f"    {pattern}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
