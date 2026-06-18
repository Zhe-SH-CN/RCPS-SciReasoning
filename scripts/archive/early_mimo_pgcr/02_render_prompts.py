#!/usr/bin/env python3
"""
Render sample baseline and pattern prompts for one target paper.

Reads from data/scireasoning/eval_neurips_2025_oral.jsonl and outputs:
- results/setup/sample_baseline_prompt.md
- results/setup/sample_pattern_prompt.md
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "results" / "setup"

# Innovation patterns for PGCR method
PATTERNS = [
    {
        "id": "gap_driven_reframing",
        "name": "Gap-Driven Reframing",
        "description": "Start from a concrete empirical, operational, or assumption gap and reframe the problem so different tools or objectives become applicable.",
        "instruction": "Look at the predecessor papers and identify a specific limitation, gap, or mismatched assumption. Reframe the problem so that a different set of methods or objectives becomes applicable.",
    },
    {
        "id": "cross_domain_synthesis",
        "name": "Cross-Domain Synthesis",
        "description": "Import ideas, methods, or formalisms from a different field to solve the target problem.",
        "instruction": "Consider how ideas, methods, or formalisms from a different research domain could be imported to solve the problem described by the predecessors.",
    },
    {
        "id": "representation_shift",
        "name": "Representation Shift",
        "description": "Replace a core primitive, data structure, or representation to simplify the problem or unlock new capabilities.",
        "instruction": "Identify a core primitive, data structure, or representation used by the predecessors. Propose replacing it with something that simplifies the problem or unlocks new capabilities.",
    },
    {
        "id": "data_evaluation_engineering",
        "name": "Data & Evaluation Engineering",
        "description": "Create new datasets, benchmarks, or evaluation protocols that reveal gaps in existing work.",
        "instruction": "Design a new dataset, benchmark, or evaluation protocol that would reveal gaps in the existing approaches described by the predecessors.",
    },
    {
        "id": "formal_experimental_tightening",
        "name": "Formal-Experimental Tightening",
        "description": "Strengthen theoretical claims with tighter bounds or validate theory with carefully designed experiments.",
        "instruction": "Identify theoretical claims in the predecessors that could be tightened with formal analysis, or propose experiments that would validate or challenge existing theory.",
    },
]


def format_predecessors(predecessors: list[dict]) -> str:
    """Format predecessor list into readable text."""
    lines = []
    for i, pw in enumerate(predecessors, 1):
        title = pw.get("title", "Unknown")
        role = pw.get("role", "")
        rel = pw.get("relationship_sentence", "")
        lines.append(f"{i}. **{title}**")
        if role:
            lines.append(f"   - Role: {role}")
        if rel:
            lines.append(f"   - Relationship: {rel}")
    return "\n".join(lines)


def render_baseline_prompt(record: dict) -> str:
    """Render a vanilla baseline prompt for idea generation."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = f"""You are an expert AI researcher. Given the following set of predecessor papers that influenced a research direction, generate 10 distinct research ideas that could advance this direction.

## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis}

## Task

Generate exactly 10 research ideas that could be the next step in this research direction. Each idea should:

1. Build directly on the predecessors listed above.
2. Be specific enough that another researcher could evaluate whether it is worth pursuing.
3. Address a clear gap, limitation, or opportunity identified in the predecessors.

## Output Format

Return a JSON array of exactly 10 objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses

Return ONLY the JSON array, no other text.
"""
    return prompt


def render_pattern_prompt(record: dict, pattern: dict) -> str:
    """Render a pattern-conditioned prompt for idea generation."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = f"""You are an expert AI researcher specializing in the "{pattern['name']}" innovation pattern.

## Innovation Pattern: {pattern['name']}

{pattern['description']}

**How to apply this pattern:** {pattern['instruction']}

## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis}

## Task

Using the "{pattern['name']}" innovation pattern, generate 5 distinct research ideas that could advance the research direction described by the predecessors above.

Each idea must:
1. Clearly apply the "{pattern['name']}" pattern.
2. Build directly on the predecessors listed above.
3. Be specific enough that another researcher could evaluate whether it is worth pursuing.
4. Address a clear gap, limitation, or opportunity identified in the predecessors.

## Output Format

Return a JSON array of exactly 5 objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses
- "pattern_application": How the "{pattern['name']}" pattern specifically informed this idea

Return ONLY the JSON array, no other text.
"""
    return prompt


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load first record
    with open(DATA_PATH) as f:
        first_line = f.readline()
    record = json.loads(first_line)

    print(f"Target paper: {record['title'][:80]}")
    print(f"Predecessors: {len(record.get('predecessors', []))}")
    print(f"Primary pattern: {record.get('primary_pattern', 'N/A')}")

    # Render baseline prompt
    baseline = render_baseline_prompt(record)
    baseline_path = OUTPUT_DIR / "sample_baseline_prompt.md"
    with open(baseline_path, "w") as f:
        f.write(f"# Sample Baseline Prompt\n\n")
        f.write(f"Target: {record['title']}\n\n")
        f.write(f"---\n\n")
        f.write(baseline)
    print(f"\nBaseline prompt: {len(baseline)} chars -> {baseline_path}")

    # Render pattern prompt (use first pattern)
    pattern = PATTERNS[0]
    pattern_prompt = render_pattern_prompt(record, pattern)
    pattern_path = OUTPUT_DIR / "sample_pattern_prompt.md"
    with open(pattern_path, "w") as f:
        f.write(f"# Sample Pattern Prompt ({pattern['name']})\n\n")
        f.write(f"Target: {record['title']}\n\n")
        f.write(f"---\n\n")
        f.write(pattern_prompt)
    print(f"Pattern prompt: {len(pattern_prompt)} chars -> {pattern_path}")

    # Verify prompts are reasonable length
    print(f"\nPrompt lengths:")
    print(f"  Baseline: {len(baseline):,} chars (~{len(baseline)//4:,} tokens)")
    print(f"  Pattern:  {len(pattern_prompt):,} chars (~{len(pattern_prompt)//4:,} tokens)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
