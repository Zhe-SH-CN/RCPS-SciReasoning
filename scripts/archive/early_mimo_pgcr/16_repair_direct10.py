#!/usr/bin/env python3
"""
Repair Direct-10 completeness for 4 zero-idea targets.

Targets to repair:
- Gq4Gay8rDB: truncated JSON, has partial ideas
- m7MD0sa8Re: truncated JSON with markdown fences, has partial ideas
- oJ84bedrtM: empty raw output, needs regeneration
- zwCb9cKHpd: truncated JSON, has partial ideas

Strategy:
1. Try robust parsing on existing raw output to extract complete ideas.
2. For targets that still have <10 ideas, regenerate with shorter max_tokens
   or per-idea generation.
3. Rejudge all repaired ideas with enriched contributions.

Output: results/direct10_complete_mimo_v25pro.json
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from mimo_client import chat_completion

ZERO_TARGETS = ['Gq4Gay8rDB', 'm7MD0sa8Re', 'oJ84bedrtM', 'zwCb9cKHpd']

GENERATION_PROMPT = """You are an expert AI researcher. Given the following set of predecessor papers that influenced a research direction, generate exactly 10 distinct research ideas that could advance this direction.

## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis_narrative}

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

Return ONLY the JSON array, no other text. Keep each idea concise."""

JUDGE_PROMPT = """You are an expert AI research evaluator. Determine whether a generated research idea is a semantic match for a target published paper.

## Target Paper

**Title:** {target_title}
**Contribution:** {target_contribution}

## Generated Idea

**Title:** {idea_title}
**Description:** {idea_description}
**Key Innovation:** {key_innovation}
**Addressed Gap:** {addressed_gap}

## Task

Determine if this generated idea captures the same core research direction as the target paper. Consider:
- Is the core problem/approach similar?
- Would a researcher reading both recognize them as the same research direction?
- Ignore superficial wording differences; focus on semantic overlap.

## Output Format

Return ONLY a compact JSON object (no markdown fences):
{{"match": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}

Keep the reason under 20 words."""


def format_predecessors(predecessors: list[dict]) -> str:
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


def robust_parse_ideas(text: str) -> list[dict]:
    """Extract complete ideas from potentially truncated JSON arrays."""
    if not text:
        return []

    # Strip markdown fences
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    # Try direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict) and "idea_title" in item]
    except json.JSONDecodeError:
        pass

    # Find the array start
    bracket_start = text.find("[")
    if bracket_start == -1:
        return []

    text = text[bracket_start:]

    # Try to extract complete objects using regex
    ideas = []
    # Pattern: match complete JSON objects with idea_title
    obj_pattern = re.compile(
        r'\{\s*"idea_title"\s*:\s*"([^"]*)"[^}]*?"idea_description"\s*:\s*"([^"]*)"[^}]*?"key_innovation"\s*:\s*"([^"]*)"[^}]*?"addressed_gap"\s*:\s*"([^"]*)"',
        re.DOTALL
    )

    for match in obj_pattern.finditer(text):
        ideas.append({
            "idea_title": match.group(1),
            "idea_description": match.group(2),
            "key_innovation": match.group(3),
            "addressed_gap": match.group(4),
        })

    if ideas:
        return ideas

    # Fallback: try to fix truncated JSON by finding complete objects
    # Split by "idea_title" boundaries
    parts = text.split('"idea_title"')
    for part in parts[1:]:  # Skip first part (before first idea_title)
        # Try to reconstruct a JSON object
        obj_text = '{"idea_title"' + part
        # Find the last complete closing brace
        brace_count = 0
        last_complete = -1
        for i, c in enumerate(obj_text):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_complete = i
                    break

        if last_complete > 0:
            try:
                obj = json.loads(obj_text[:last_complete + 1])
                if "idea_title" in obj and "idea_description" in obj:
                    ideas.append({
                        "idea_title": obj.get("idea_title", ""),
                        "idea_description": obj.get("idea_description", ""),
                        "key_innovation": obj.get("key_innovation", ""),
                        "addressed_gap": obj.get("addressed_gap", ""),
                    })
            except json.JSONDecodeError:
                continue

    return ideas


def generate_ideas(record: dict, model: str, sleep_seconds: float) -> dict:
    """Generate 10 ideas for a target paper."""
    predecessors_text = format_predecessors(record.get("predecessors", []))
    synthesis = record.get("synthesis_narrative", "")

    prompt = GENERATION_PROMPT.format(
        predecessors_text=predecessors_text,
        synthesis_narrative=synthesis,
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.7, max_tokens=4096,
        sleep_seconds=sleep_seconds,
    )

    raw_content = result["content"]
    ideas = robust_parse_ideas(raw_content)

    return {
        "raw_output": raw_content,
        "parsed_ideas": ideas,
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "finish_reason": result.get("finish_reason"),
    }


def judge_idea(idea: dict, target_title: str, target_contribution: str,
               model: str, sleep_seconds: float) -> dict:
    """Judge whether one idea matches the target paper."""
    prompt = JUDGE_PROMPT.format(
        target_title=target_title,
        target_contribution=target_contribution,
        idea_title=idea.get("idea_title", ""),
        idea_description=idea.get("idea_description", ""),
        key_innovation=idea.get("key_innovation", ""),
        addressed_gap=idea.get("addressed_gap", ""),
    )

    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(
        messages, model=model, temperature=0.0, max_tokens=256,
        sleep_seconds=sleep_seconds,
    )

    raw = result["content"]
    # Strip markdown fences if present
    raw_clean = raw.strip()
    if raw_clean.startswith("```"):
        raw_clean = re.sub(r"^```(?:json)?\s*\n?", "", raw_clean)
        raw_clean = re.sub(r"\n?```\s*$", "", raw_clean)
        raw_clean = raw_clean.strip()

    judgment = {
        "match": False,
        "confidence": 0.0,
        "reason": "",
        "raw_response": raw,
        "parse_status": "unknown",
    }

    try:
        parsed = json.loads(raw_clean)
        if isinstance(parsed, dict):
            judgment["match"] = bool(parsed.get("match", False))
            judgment["confidence"] = float(parsed.get("confidence", 0.0))
            judgment["reason"] = str(parsed.get("reason", ""))[:200]
            judgment["parse_status"] = "ok"
        else:
            judgment["parse_status"] = "not_dict"
    except json.JSONDecodeError:
        judgment["parse_status"] = "json_error"

    judgment["input_tokens"] = result.get("input_tokens")
    judgment["output_tokens"] = result.get("output_tokens")
    judgment["finish_reason"] = result.get("finish_reason")
    return judgment


def main():
    parser = argparse.ArgumentParser(description="Repair Direct-10 completeness")
    parser.add_argument("--baseline", default=str(PROJECT_ROOT / "results" / "baseline_mimo.json"))
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"))
    parser.add_argument("--report", default=str(PROJECT_ROOT / "results" / "direct10_repair_report.md"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no API calls")
    args = parser.parse_args()

    output_path = Path(args.output)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load baseline
    with open(args.baseline) as f:
        baseline = json.load(f)

    # Load enriched eval data
    eval_data = {}
    with open(args.eval_data) as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                eval_data[rec["target_id"]] = rec

    print(f"Loaded {len(baseline['targets'])} baseline targets")
    print(f"Loaded {len(eval_data)} enriched eval records")

    # Identify zero-idea targets
    zero_targets = []
    for t in baseline['targets']:
        ideas = t.get('generated_ideas', [])
        if len(ideas) == 0:
            zero_targets.append(t['target_id'])

    print(f"Zero-idea targets: {len(zero_targets)}")
    for tid in zero_targets:
        print(f"  {tid}")

    # First pass: try robust parsing on existing raw output
    repair_log = []
    for t in baseline['targets']:
        if t['target_id'] not in zero_targets:
            continue

        gen = t.get('generation', {})
        raw = gen.get('raw_output', '')
        ideas = robust_parse_ideas(raw)

        repair_log.append({
            'target_id': t['target_id'],
            'target_title': t.get('target_title', ''),
            'original_ideas': 0,
            'robust_parsed': len(ideas),
            'raw_length': len(raw),
            'action': 'robust_parse' if len(ideas) >= 10 else 'regenerate',
        })

        if len(ideas) >= 10:
            t['generated_ideas'] = ideas[:10]
            print(f"  {t['target_id']}: robust parse found {len(ideas)} ideas (using 10)")
        else:
            print(f"  {t['target_id']}: robust parse found {len(ideas)} ideas (need regeneration)")

    # All zero-idea targets need regeneration to get exactly 10 ideas
    still_zero = [t for t in baseline['targets'] if t['target_id'] in zero_targets]
    print(f"\nNeed regeneration: {len(still_zero)} targets")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        for entry in repair_log:
            print(f"  {entry['target_id']}: {entry['action']} ({entry['robust_parsed']} parsed)")
        return

    # Regenerate for targets that still need it
    for t in still_zero:
        target_id = t['target_id']
        eval_rec = eval_data.get(target_id, {})
        print(f"\nRegenerating {target_id}: {t.get('target_title', '')[:60]}...")

        try:
            gen_result = generate_ideas(eval_rec, args.model, args.sleep_seconds)
            ideas = gen_result['parsed_ideas']
            print(f"  Generated {len(ideas)} ideas")

            t['generated_ideas'] = ideas
            t['generation'] = {
                'raw_output': gen_result['raw_output'][:2000],
                'input_tokens': gen_result.get('input_tokens'),
                'output_tokens': gen_result.get('output_tokens'),
                'elapsed_seconds': gen_result.get('elapsed_seconds'),
                'finish_reason': gen_result.get('finish_reason'),
            }

            # Update repair log
            for entry in repair_log:
                if entry['target_id'] == target_id:
                    entry['robust_parsed'] = len(ideas)
                    entry['action'] = 'regenerated'

        except Exception as e:
            print(f"  FAILED: {e}")
            for entry in repair_log:
                if entry['target_id'] == target_id:
                    entry['action'] = f'failed: {str(e)[:100]}'

    # Now judge ALL targets with enriched contributions
    print("\n=== Judging all targets with enriched contributions ===")
    total_judgments = 0
    total_hits = 0

    for t in baseline['targets']:
        target_id = t['target_id']
        eval_rec = eval_data.get(target_id, {})
        target_title = eval_rec.get('title', t.get('target_title', ''))
        target_contribution = eval_rec.get('contribution', '')
        if not target_contribution:
            target_contribution = target_title

        ideas = t.get('generated_ideas', [])
        if not ideas:
            continue

        print(f"\nJudging {target_id}: {len(ideas)} ideas")

        judgments = []
        hit = False
        for idea_idx, idea in enumerate(ideas):
            try:
                judgment = judge_idea(
                    idea, target_title, target_contribution,
                    args.model, args.sleep_seconds,
                )
                judgment['idea_index'] = idea_idx
                judgments.append(judgment)
                if judgment.get('match'):
                    hit = True
            except Exception as e:
                judgments.append({
                    'idea_index': idea_idx,
                    'match': False,
                    'confidence': 0.0,
                    'reason': str(e)[:200],
                    'parse_status': 'error',
                })

        t['judgments'] = judgments
        t['hit'] = hit
        t['timestamp'] = datetime.now().isoformat()

        total_judgments += len(judgments)
        if hit:
            total_hits += 1
            print(f"  HIT!")
        else:
            print(f"  MISS")

    # Save repaired baseline
    baseline['method'] = 'direct10_complete'
    baseline['repaired_targets'] = zero_targets
    baseline['repaired_timestamp'] = datetime.now().isoformat()

    with open(output_path, 'w') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Generate repair report
    with open(report_path, 'w') as f:
        f.write("# Direct-10 Repair Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Zero-idea targets: {len(zero_targets)}\n")
        f.write(f"- Repaired by robust parsing: {sum(1 for e in repair_log if e['action'] == 'robust_parse')}\n")
        f.write(f"- Repaired by regeneration: {sum(1 for e in repair_log if e['action'] == 'regenerated')}\n")
        f.write(f"- Failed: {sum(1 for e in repair_log if 'failed' in e['action'])}\n\n")

        f.write("## Target Details\n\n")
        f.write("| Target ID | Title | Original | Repaired | Action |\n")
        f.write("|---|---|---:|---:|---|\n")
        for entry in repair_log:
            title_short = entry['target_title'][:40]
            f.write(f"| {entry['target_id']} | {title_short} | {entry['original_ideas']} | {entry['robust_parsed']} | {entry['action']} |\n")

        f.write("\n## Validation\n\n")
        total_ideas = sum(len(t.get('generated_ideas', [])) for t in baseline['targets'])
        targets_with_10 = sum(1 for t in baseline['targets'] if len(t.get('generated_ideas', [])) == 10)
        total_judgments_all = sum(len(t.get('judgments', [])) for t in baseline['targets'])
        f.write(f"- Total targets: {len(baseline['targets'])}\n")
        f.write(f"- Targets with 10 ideas: {targets_with_10}\n")
        f.write(f"- Total ideas: {total_ideas}\n")
        f.write(f"- Total judgments: {total_judgments_all}\n")
        f.write(f"- Repaired target judgments: {total_judgments}\n")
        f.write(f"- Repaired target hits: {total_hits}\n")

    print(f"Saved: {report_path}")

    # Final validation
    targets_with_10 = sum(1 for t in baseline['targets'] if len(t.get('generated_ideas', [])) == 10)
    print(f"\n=== Final Validation ===")
    print(f"Targets with 10 ideas: {targets_with_10}/77")
    if targets_with_10 == 77:
        print("SUCCESS: All 77 targets have exactly 10 ideas")
    else:
        print(f"WARNING: {77 - targets_with_10} targets still don't have 10 ideas")


if __name__ == "__main__":
    sys.exit(main())
