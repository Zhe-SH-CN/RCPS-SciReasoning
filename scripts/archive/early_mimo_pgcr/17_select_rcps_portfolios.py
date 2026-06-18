#!/usr/bin/env python3
"""
Select RCPS portfolios from Direct-10 and BCS-50 candidates.

Creates:
- RCPS-8/2: 8 Direct anchors + 2 expansion candidates
- RCPS-5/5: 5 Direct anchors + 5 expansion candidates
- Random portfolio: random selection from expansion
- Diversity-only portfolio: diversity-based selection

Output: JSONL files with selected ideas and slot source labels.
"""

import json
import re
import sys
import argparse
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file."""
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def normalize_text(text: str) -> set:
    """Extract content words from text."""
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                 'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
                 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                 'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
                 'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
                 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'both',
                 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
                 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
                 'and', 'but', 'or', 'if', 'while', 'that', 'this', 'which', 'who',
                 'whom', 'what', 'when', 'where', 'why', 'how', 'its', 'it'}
    words = set(re.findall(r'\w+', text.lower()))
    return words - stopwords


def jaccard_similarity(set1: set, set2: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def compute_idea_features(idea: dict, direct_ideas: list[dict], predecessors: list[dict]) -> dict:
    """Compute target-hidden diagnostic features for an idea."""
    idea_text = idea.get('idea_title', '') + ' ' + idea.get('idea_description', '')
    idea_words = normalize_text(idea_text)

    # Lexical specificity: content-word count
    lexical_specificity = len(idea_words)

    # Predecessor coverage: overlap with predecessor titles
    pred_words = set()
    for p in predecessors:
        pred_words |= normalize_text(p.get('title', ''))
    pred_coverage = len(idea_words & pred_words) / max(len(pred_words), 1)

    # Anchor novelty: low overlap with Direct ideas
    anchor_overlaps = []
    for d in direct_ideas:
        d_text = d.get('idea_title', '') + ' ' + d.get('idea_description', '')
        d_words = normalize_text(d_text)
        anchor_overlaps.append(jaccard_similarity(idea_words, d_words))
    anchor_novelty = 1.0 - (sum(anchor_overlaps) / max(len(anchor_overlaps), 1)) if anchor_overlaps else 1.0

    return {
        'lexical_specificity': lexical_specificity,
        'predecessor_coverage': pred_coverage,
        'anchor_novelty': anchor_novelty,
        'idea_words': idea_words,
    }


def compute_composite_score(features: dict, weights: dict) -> float:
    """Compute composite score from features and weights."""
    score = 0.0
    score += weights.get('lexical_specificity_weight', 0.3) * min(features['lexical_specificity'] / 50, 1.0)
    score += weights.get('predecessor_coverage_weight', 0.3) * features['predecessor_coverage']
    score += weights.get('anchor_novelty_weight', 0.2) * features['anchor_novelty']
    return score


def selector_diagnostics(cand: dict) -> dict:
    """Return JSON-serializable diagnostics used by the deterministic selector."""
    features = cand.get('_features', {})
    composite_score = cand.get('_score')
    return {
        'lexical_specificity': features.get('lexical_specificity', 0),
        'predecessor_coverage': round(features.get('predecessor_coverage', 0.0), 4),
        'anchor_novelty': round(features.get('anchor_novelty', 0.0), 4),
        'composite_score': round(composite_score, 4) if composite_score is not None else None,
    }


def public_idea_copy(idea: dict) -> dict:
    """Copy an idea without private selector scratch fields."""
    return {k: v for k, v in idea.items() if not k.startswith('_')}


def select_diverse_subset(candidates: list[dict], n: int, threshold: float = 0.6) -> list[dict]:
    """Select diverse subset using greedy Jaccard dedup."""
    selected = []
    selected_words = []

    for cand in candidates:
        if len(selected) >= n:
            break

        cand_words = cand.get('_features', {}).get('idea_words', set())
        if any(jaccard_similarity(cand_words, sw) > threshold for sw in selected_words):
            continue

        selected.append(cand)
        selected_words.append(cand_words)

    return selected


def select_rcps_portfolio(direct_ideas: list[dict], expansion_candidates: list[dict],
                          k_direct: int, n_expansion: int, weights: dict,
                          threshold: float = 0.6, predecessors: list[dict] | None = None) -> list[dict]:
    """Select RCPS portfolio with k direct anchors and n expansion candidates."""
    predecessors = predecessors or []

    # Take first k direct ideas
    direct_slots = []
    for idea in direct_ideas[:k_direct]:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'direct'
        direct_slots.append(idea_copy)

    candidate_pool = [public_idea_copy(c) for c in expansion_candidates]

    # Compute features for expansion candidates
    for cand in candidate_pool:
        cand['_features'] = compute_idea_features(cand, direct_slots, predecessors)

    # Score expansion candidates
    for cand in candidate_pool:
        cand['_score'] = compute_composite_score(cand['_features'], weights)

    # Sort by score (descending)
    candidate_pool.sort(key=lambda x: x.get('_score', 0), reverse=True)

    # Select diverse expansion candidates
    expansion_slots = select_diverse_subset(candidate_pool, n_expansion, threshold)
    for idea in expansion_slots:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'expansion'
        idea_copy['selector_diagnostics'] = selector_diagnostics(idea)
        direct_slots.append(idea_copy)

    return direct_slots


def select_random_portfolio(direct_ideas: list[dict], expansion_candidates: list[dict],
                            k_direct: int, n_expansion: int, seed: int = 42) -> list[dict]:
    """Select random portfolio for ablation."""
    rng = random.Random(seed)

    # Take first k direct ideas
    direct_slots = []
    for idea in direct_ideas[:k_direct]:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'direct'
        direct_slots.append(idea_copy)

    # Random selection from expansion
    candidate_pool = [public_idea_copy(c) for c in expansion_candidates]
    if len(expansion_candidates) >= n_expansion:
        selected = rng.sample(candidate_pool, n_expansion)
    else:
        selected = candidate_pool[:n_expansion]

    for idea in selected:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'expansion_random'
        direct_slots.append(idea_copy)

    return direct_slots


def select_diversity_portfolio(direct_ideas: list[dict], expansion_candidates: list[dict],
                               k_direct: int, n_expansion: int, threshold: float = 0.6,
                               predecessors: list[dict] | None = None) -> list[dict]:
    """Select diversity-only portfolio (no LLM scoring)."""
    predecessors = predecessors or []

    # Take first k direct ideas
    direct_slots = []
    for idea in direct_ideas[:k_direct]:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'direct'
        direct_slots.append(idea_copy)

    candidate_pool = [public_idea_copy(c) for c in expansion_candidates]

    # Compute features for expansion candidates
    for cand in candidate_pool:
        cand['_features'] = compute_idea_features(cand, direct_slots, predecessors)

    # Select by diversity only (no scoring)
    expansion_slots = select_diverse_subset(candidate_pool, n_expansion, threshold)
    for idea in expansion_slots:
        idea_copy = public_idea_copy(idea)
        idea_copy['slot_source'] = 'expansion_diverse'
        idea_copy['selector_diagnostics'] = selector_diagnostics(idea)
        direct_slots.append(idea_copy)

    return direct_slots


def main():
    parser = argparse.ArgumentParser(description="Select RCPS portfolios")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "results" / "rcps_preregistered_config.json"))
    parser.add_argument("--d10", default=str(PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"))
    parser.add_argument("--bcs-candidates", default=str(PROJECT_ROOT / "results" / "bcs50_candidates_mimo_v25pro.jsonl"))
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "results"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    with open(args.config) as f:
        config = json.load(f)
    print(f"Loaded config: {config['main_method']}")

    # Load Direct-10
    with open(args.d10) as f:
        d10 = json.load(f)
    d10_lookup = {t['target_id']: t for t in d10['targets']}
    print(f"Loaded Direct-10: {len(d10_lookup)} targets")

    # Load BCS candidates
    bcs_candidates = load_jsonl(args.bcs_candidates)
    bcs_lookup = {t['target_id']: t for t in bcs_candidates}
    print(f"Loaded BCS candidates: {len(bcs_lookup)} targets")

    # Load eval data
    eval_data = {}
    with open(args.eval_data) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_data[rec['target_id']] = rec
    print(f"Loaded eval data: {len(eval_data)} targets")

    # Get config values
    weights = config['selector_features']
    threshold = config['duplicate_threshold']
    seed = config['random_seeds']['random_portfolio']

    # Create portfolios for each method
    methods = {
        'rcps82': {'direct': 8, 'expansion': 2},
        'rcps55': {'direct': 5, 'expansion': 5},
    }

    for method_name, slots in methods.items():
        print(f"\n=== {method_name} ===")
        k_direct = slots['direct']
        n_expansion = slots['expansion']

        portfolio_results = []
        for target_id in d10_lookup:
            d10_t = d10_lookup[target_id]
            bcs_t = bcs_lookup.get(target_id, {})
            eval_rec = eval_data.get(target_id, {})

            direct_ideas = d10_t.get('generated_ideas', [])
            expansion_candidates = bcs_t.get('candidates', [])
            predecessors = eval_rec.get('predecessors', [])

            # Select RCPS portfolio
            selected = select_rcps_portfolio(
                direct_ideas, expansion_candidates,
                k_direct, n_expansion, weights, threshold, predecessors
            )

            # Count slots
            direct_count = sum(1 for s in selected if s.get('slot_source') == 'direct')
            expansion_count = sum(1 for s in selected if s.get('slot_source') == 'expansion')

            result = {
                'target_id': target_id,
                'total_selected': len(selected),
                'direct_slots': direct_count,
                'expansion_slots': expansion_count,
                'selector_metadata': {
                    'uses_target_title': False,
                    'uses_target_contribution': False,
                    'predecessor_count': len(predecessors),
                    'duplicate_threshold': threshold,
                },
                'selected': selected,
            }
            portfolio_results.append(result)

        # Save
        output_path = output_dir / f"{method_name}_selected_mimo_v25pro.jsonl"
        with open(output_path, 'w') as f:
            for r in portfolio_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print(f"Saved: {output_path}")

    # Random portfolio
    print(f"\n=== random-portfolio ===")
    random_results = []
    for target_id in d10_lookup:
        d10_t = d10_lookup[target_id]
        bcs_t = bcs_lookup.get(target_id, {})
        eval_rec = eval_data.get(target_id, {})

        direct_ideas = d10_t.get('generated_ideas', [])
        expansion_candidates = bcs_t.get('candidates', [])

        selected = select_random_portfolio(
            direct_ideas, expansion_candidates,
            8, 2, seed
        )

        random_results.append({
            'target_id': target_id,
            'total_selected': len(selected),
            'direct_slots': 8,
            'expansion_slots': 2,
            'selector_metadata': {
                'uses_target_title': False,
                'uses_target_contribution': False,
                'random_seed': seed,
            },
            'selected': selected,
        })

    output_path = output_dir / "random_portfolio_selected_mimo_v25pro.jsonl"
    with open(output_path, 'w') as f:
        for r in random_results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"Saved: {output_path}")

    # Diversity-only portfolio
    print(f"\n=== diversity-only ===")
    diversity_results = []
    for target_id in d10_lookup:
        d10_t = d10_lookup[target_id]
        bcs_t = bcs_lookup.get(target_id, {})
        eval_rec = eval_data.get(target_id, {})

        direct_ideas = d10_t.get('generated_ideas', [])
        expansion_candidates = bcs_t.get('candidates', [])
        predecessors = eval_rec.get('predecessors', [])

        selected = select_diversity_portfolio(
            direct_ideas, expansion_candidates,
            8, 2, threshold, predecessors
        )

        diversity_results.append({
            'target_id': target_id,
            'total_selected': len(selected),
            'direct_slots': 8,
            'expansion_slots': 2,
            'selector_metadata': {
                'uses_target_title': False,
                'uses_target_contribution': False,
                'predecessor_count': len(predecessors),
                'duplicate_threshold': threshold,
            },
            'selected': selected,
        })

    output_path = output_dir / "diversity_portfolio_selected_mimo_v25pro.jsonl"
    with open(output_path, 'w') as f:
        for r in diversity_results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"Saved: {output_path}")

    print(f"\n=== Summary ===")
    print(f"Created 4 portfolio files:")
    print(f"  - rcps82_selected_mimo_v25pro.jsonl")
    print(f"  - rcps55_selected_mimo_v25pro.jsonl")
    print(f"  - random_portfolio_selected_mimo_v25pro.jsonl")
    print(f"  - diversity_portfolio_selected_mimo_v25pro.jsonl")


if __name__ == "__main__":
    sys.exit(main())
