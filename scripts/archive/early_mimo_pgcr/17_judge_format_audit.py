#!/usr/bin/env python3
"""
Judge format audit: test strict JSON judge output on a sample of targets.

This script:
1. Selects a stratified sample of targets (Direct-only hits, BCS-only hits, overlap, both-miss)
2. Uses a strict short judge prompt with compact JSON output
3. Stores raw responses, parsed JSON, parse status, finish reason, and token usage
4. Reports parse failure rate and hit label stability

Output: results/judge_format_audit.json, results/judge_format_audit.md
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

# Strict short judge prompt
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

Return ONLY a compact JSON object (no markdown fences, no extra text):
{{"match": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}

Keep the reason under 20 words. Do not add any text before or after the JSON object."""


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
        messages, model=model, temperature=0.0, max_tokens=2048,
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
        "raw_clean": raw_clean,
        "parse_status": "unknown",
    }

    if not raw_clean:
        judgment["parse_status"] = "empty_response"
    else:
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
    judgment["elapsed_seconds"] = result.get("elapsed_seconds")
    return judgment


def select_audit_sample(d10_path: str, bcs_path: str, enriched_path: str) -> list[dict]:
    """Select a stratified sample of targets for audit."""
    with open(d10_path) as f:
        d10 = json.load(f)
    with open(bcs_path) as f:
        bcs = json.load(f)
    with open(enriched_path) as f:
        eval_data = {json.loads(line)['target_id']: json.loads(line) for line in f}

    # Build hit sets
    d10_hits = {t['target_id'] for t in d10['targets'] if t.get('hit')}
    bcs_hits = {t['target_id'] for t in bcs['targets'] if t.get('hit')}

    # Categorize targets
    direct_only = d10_hits - bcs_hits
    bcs_only = bcs_hits - d10_hits
    overlap = d10_hits & bcs_hits
    both_miss = set(t['target_id'] for t in d10['targets']) - d10_hits - bcs_hits

    # Select sample: 2 from each category
    import random
    rng = random.Random(42)

    sample = []
    for category, targets in [("direct_only", direct_only), ("bcs_only", bcs_only),
                               ("overlap", overlap), ("both_miss", both_miss)]:
        selected = rng.sample(list(targets), min(2, len(targets)))
        for tid in selected:
            d10_t = next(t for t in d10['targets'] if t['target_id'] == tid)
            bcs_t = next((t for t in bcs['targets'] if t['target_id'] == tid), None)
            eval_rec = eval_data.get(tid, {})

            # Get one idea from each method
            ideas_to_judge = []
            if d10_t.get('generated_ideas'):
                ideas_to_judge.append({
                    'source': 'direct',
                    'idea': d10_t['generated_ideas'][0],
                    'old_match': d10_t.get('judgments', [{}])[0].get('match', False) if d10_t.get('judgments') else False,
                })
            if bcs_t and bcs_t.get('selected_ideas'):
                ideas_to_judge.append({
                    'source': 'bcs',
                    'idea': bcs_t['selected_ideas'][0],
                    'old_match': bcs_t.get('judgments', [{}])[0].get('match', False) if bcs_t.get('judgments') else False,
                })

            sample.append({
                'target_id': tid,
                'category': category,
                'target_title': eval_rec.get('title', d10_t.get('target_title', '')),
                'target_contribution': eval_rec.get('contribution', ''),
                'ideas_to_judge': ideas_to_judge,
                'd10_hit': tid in d10_hits,
                'bcs_hit': tid in bcs_hits,
            })

    return sample


def main():
    parser = argparse.ArgumentParser(description="Judge format audit")
    parser.add_argument("--d10", default=str(PROJECT_ROOT / "results" / "direct10_complete_mimo_v25pro.json"))
    parser.add_argument("--bcs", default=str(PROJECT_ROOT / "results" / "bcs50_eval_mimo_v25pro.json"))
    parser.add_argument("--eval-data", default=str(PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "results" / "judge_format_audit.json"))
    parser.add_argument("--report", default=str(PROJECT_ROOT / "results" / "judge_format_audit.md"))
    parser.add_argument("--model", default="mimo-v2.5-pro")
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    args = parser.parse_args()

    output_path = Path(args.output)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Select audit sample
    print("Selecting audit sample...")
    sample = select_audit_sample(args.d10, args.bcs, args.eval_data)
    print(f"Selected {len(sample)} targets for audit")

    # Judge each idea
    audit_results = []
    total_judgments = 0
    parse_ok = 0
    parse_fail = 0
    label_changes = 0

    for entry in sample:
        print(f"\n=== {entry['target_id']} ({entry['category']}) ===")

        target_results = {
            'target_id': entry['target_id'],
            'category': entry['category'],
            'target_title': entry['target_title'][:60],
            'd10_hit': entry['d10_hit'],
            'bcs_hit': entry['bcs_hit'],
            'judgments': [],
        }

        for idea_info in entry['ideas_to_judge']:
            idea = idea_info['idea']
            print(f"  Judging {idea_info['source']} idea: {idea.get('idea_title', '')[:50]}...")

            try:
                judgment = judge_idea(
                    idea, entry['target_title'], entry['target_contribution'],
                    args.model, args.sleep_seconds,
                )
                judgment['source'] = idea_info['source']
                judgment['old_match'] = idea_info['old_match']
                judgment['new_match'] = judgment['match']
                judgment['label_changed'] = judgment['match'] != idea_info['old_match']

                total_judgments += 1
                if judgment['parse_status'] == 'ok':
                    parse_ok += 1
                else:
                    parse_fail += 1
                if judgment['label_changed']:
                    label_changes += 1

                print(f"    Parse: {judgment['parse_status']}, Match: {judgment['match']}, "
                      f"Old: {idea_info['old_match']}, Changed: {judgment['label_changed']}")

            except Exception as e:
                judgment = {
                    'source': idea_info['source'],
                    'old_match': idea_info['old_match'],
                    'new_match': False,
                    'label_changed': idea_info['old_match'],
                    'parse_status': 'error',
                    'error': str(e)[:200],
                }
                total_judgments += 1
                parse_fail += 1
                print(f"    ERROR: {e}")

            target_results['judgments'].append(judgment)

        audit_results.append(target_results)

    # Save audit results
    audit = {
        'timestamp': datetime.now().isoformat(),
        'model': args.model,
        'total_targets': len(sample),
        'total_judgments': total_judgments,
        'parse_ok': parse_ok,
        'parse_fail': parse_fail,
        'parse_rate': round(parse_ok / max(total_judgments, 1) * 100, 1),
        'label_changes': label_changes,
        'results': audit_results,
    }

    with open(output_path, 'w') as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Generate report
    with open(report_path, 'w') as f:
        f.write("# Judge Format Audit\n\n")
        f.write(f"Generated: {audit['timestamp']}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Total targets: {len(sample)}\n")
        f.write(f"- Total judgments: {total_judgments}\n")
        f.write(f"- Parse OK: {parse_ok} ({audit['parse_rate']}%)\n")
        f.write(f"- Parse fail: {parse_fail}\n")
        f.write(f"- Label changes: {label_changes}\n\n")

        f.write("## Results by Category\n\n")
        f.write("| Category | Targets | Judgments | Parse OK | Label Changes |\n")
        f.write("|---|---:|---:|---:|---:|\n")

        categories = {}
        for entry in audit_results:
            cat = entry['category']
            if cat not in categories:
                categories[cat] = {'targets': 0, 'judgments': 0, 'parse_ok': 0, 'label_changes': 0}
            categories[cat]['targets'] += 1
            for j in entry['judgments']:
                categories[cat]['judgments'] += 1
                if j.get('parse_status') == 'ok':
                    categories[cat]['parse_ok'] += 1
                if j.get('label_changed'):
                    categories[cat]['label_changes'] += 1

        for cat, stats in categories.items():
            f.write(f"| {cat} | {stats['targets']} | {stats['judgments']} | {stats['parse_ok']} | {stats['label_changes']} |\n")

        f.write("\n## Detailed Results\n\n")
        for entry in audit_results:
            f.write(f"### {entry['target_id']} ({entry['category']})\n\n")
            for j in entry['judgments']:
                f.write(f"- **{j['source']}**: parse={j.get('parse_status')}, "
                        f"match={j.get('new_match')}, old={j.get('old_match')}, "
                        f"changed={j.get('label_changed')}\n")
            f.write("\n")

    print(f"Saved: {report_path}")

    # Final summary
    print(f"\n=== Final Summary ===")
    print(f"Parse rate: {audit['parse_rate']}%")
    print(f"Label changes: {label_changes}/{total_judgments}")
    if audit['parse_rate'] >= 98:
        print("PASS: Parse rate >= 98%")
    else:
        print(f"FAIL: Parse rate < 98%")


if __name__ == "__main__":
    sys.exit(main())
