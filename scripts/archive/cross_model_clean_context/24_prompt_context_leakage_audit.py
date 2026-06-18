#!/usr/bin/env python3
"""
Prompt context leakage audit.

Audits legacy and clean generation contexts for target-derived bridge text.

Legacy context: predecessor title, role, relationship_sentence, synthesis_narrative
Clean context: predecessor titles only

Output:
  results/prompt_context_leakage_audit_2026-06-14.json
  results/prompt_context_leakage_audit_2026-06-14.md
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_title_prefix(title: str, min_len: int = 4) -> str:
    """Get title prefix before first colon, if length >= min_len."""
    if ":" in title:
        prefix = title.split(":")[0].strip()
        if len(prefix) >= min_len:
            return prefix
    return ""


def normalize_for_match(text: str) -> str:
    """Normalize text for matching: lowercase, collapse whitespace."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def check_exact_match(context: str, target_text: str) -> bool:
    """Check if target text appears exactly in context."""
    if not target_text:
        return False
    return normalize_for_match(target_text) in normalize_for_match(context)


def check_prefix_match(context: str, prefix: str) -> bool:
    """Check if title prefix appears in context."""
    if not prefix:
        return False
    return normalize_for_match(prefix) in normalize_for_match(context)


def build_legacy_context(rec: dict) -> str:
    """Build legacy generation context (predecessor title, role, rel, synthesis)."""
    lines = []
    for i, p in enumerate(rec.get("predecessors", []), 1):
        title = p.get("title", "Unknown")
        role = p.get("role", "")
        rel = p.get("relationship_sentence", "")
        lines.append(f"{i}. **{title}**")
        if role:
            lines.append(f"   - Role: {role}")
        if rel:
            lines.append(f"   - Relationship: {rel}")

    predecessors_text = "\n".join(lines)
    synthesis = rec.get("synthesis_narrative", "")

    return f"""## Predecessor Papers

{predecessors_text}

## Synthesis Narrative

{synthesis}"""


def build_clean_context(rec: dict) -> str:
    """Build clean generation context (predecessor titles only)."""
    lines = []
    for i, p in enumerate(rec.get("predecessors", []), 1):
        title = p.get("title", "Unknown")
        lines.append(f"{i}. {title}")

    predecessors_text = "\n".join(lines)

    return f"""## Predecessor Papers

{predecessors_text}"""


def audit_context(context: str, target_title: str, target_contribution: str,
                  target_abstract: str, title_prefix: str) -> dict:
    """Audit a single context for leakage."""
    result = {
        "exact_title_match": check_exact_match(context, target_title),
        "exact_contribution_match": check_exact_match(context, target_contribution),
        "exact_abstract_match": check_exact_match(context, target_abstract) if target_abstract else False,
        "title_prefix_match": check_prefix_match(context, title_prefix) if title_prefix else False,
    }
    result["any_leakage"] = any(result.values())
    return result


def main():
    # Load data
    enriched_path = PROJECT_ROOT / "data" / "scireasoning" / "eval_neurips_2025_oral_enriched.jsonl"
    records = []
    with open(enriched_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} records")

    # Audit both context modes
    modes = {
        "legacy": {
            "description": "Predecessor title + role + relationship_sentence + synthesis_narrative",
            "unsafe_fields": ["synthesis_narrative", "predecessor.role", "predecessor.relationship_sentence"],
            "build": build_legacy_context,
        },
        "clean": {
            "description": "Predecessor titles only",
            "unsafe_fields": [],
            "build": build_clean_context,
        },
    }

    audit_results = {}

    for mode_name, mode_info in modes.items():
        print(f"\n=== {mode_name} context ===")

        title_matches = 0
        contribution_matches = 0
        abstract_matches = 0
        prefix_matches = 0
        any_leakage = 0
        flagged_examples = []

        for rec in records:
            context = mode_info["build"](rec)
            target_title = rec.get("title", "")
            target_contribution = rec.get("contribution", "")
            target_abstract = rec.get("abstract", "")
            title_prefix = get_title_prefix(target_title)

            leakage = audit_context(context, target_title, target_contribution,
                                    target_abstract, title_prefix)

            if leakage["exact_title_match"]:
                title_matches += 1
            if leakage["exact_contribution_match"]:
                contribution_matches += 1
            if leakage["exact_abstract_match"]:
                abstract_matches += 1
            if leakage["title_prefix_match"]:
                prefix_matches += 1
            if leakage["any_leakage"]:
                any_leakage += 1
                if len(flagged_examples) < 5:
                    flagged_examples.append({
                        "target_id": rec["target_id"],
                        "target_title": target_title[:80],
                        "title_prefix": title_prefix,
                        "leakage": leakage,
                        "context_preview": context[:300],
                    })

        total = len(records)
        # Determine PASS/FAIL
        has_unsafe_fields = len(mode_info["unsafe_fields"]) > 0
        has_exact_matches = title_matches > 0 or contribution_matches > 0 or abstract_matches > 0
        status = "FAIL" if (has_unsafe_fields or has_exact_matches) else "PASS"

        audit_results[mode_name] = {
            "status": status,
            "description": mode_info["description"],
            "unsafe_fields": mode_info["unsafe_fields"],
            "total_targets": total,
            "exact_title_matches": title_matches,
            "exact_contribution_matches": contribution_matches,
            "exact_abstract_matches": abstract_matches,
            "title_prefix_matches": prefix_matches,
            "any_leakage_count": any_leakage,
            "flagged_examples": flagged_examples,
        }

        print(f"  Status: {status}")
        print(f"  Unsafe fields: {mode_info['unsafe_fields']}")
        print(f"  Exact title matches: {title_matches}/{total}")
        print(f"  Exact contribution matches: {contribution_matches}/{total}")
        print(f"  Title prefix matches: {prefix_matches}/{total}")
        print(f"  Any leakage: {any_leakage}/{total}")

    # Save JSON
    audit = {
        "timestamp": datetime.now().isoformat(),
        "input_file": str(enriched_path.name),
        "total_records": len(records),
        "modes": audit_results,
    }

    json_path = PROJECT_ROOT / "results" / "prompt_context_leakage_audit_2026-06-14.json"
    with open(json_path, "w") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {json_path}")

    # Save Markdown
    md_path = PROJECT_ROOT / "results" / "prompt_context_leakage_audit_2026-06-14.md"
    with open(md_path, "w") as f:
        f.write("# Prompt Context Leakage Audit\n\n")
        f.write(f"Generated: {audit['timestamp']}\n\n")

        f.write("## Summary\n\n")
        f.write("| Context Mode | Status | Unsafe Fields | Title Matches | Prefix Matches | Any Leakage |\n")
        f.write("|---|---|---|---:|---:|---:|\n")
        for mode_name, r in audit_results.items():
            unsafe = ", ".join(r["unsafe_fields"]) if r["unsafe_fields"] else "none"
            f.write(f"| {mode_name} | **{r['status']}** | {unsafe} | {r['exact_title_matches']}/{r['total_targets']} | {r['title_prefix_matches']}/{r['total_targets']} | {r['any_leakage_count']}/{r['total_targets']} |\n")
        f.write("\n")

        for mode_name, r in audit_results.items():
            f.write(f"## {mode_name.title()} Context\n\n")
            f.write(f"- Description: {r['description']}\n")
            f.write(f"- Status: **{r['status']}**\n")
            f.write(f"- Total targets: {r['total_targets']}\n")
            f.write(f"- Exact title matches: {r['exact_title_matches']}\n")
            f.write(f"- Exact contribution matches: {r['exact_contribution_matches']}\n")
            f.write(f"- Exact abstract matches: {r['exact_abstract_matches']}\n")
            f.write(f"- Title prefix matches: {r['title_prefix_matches']}\n")
            f.write(f"- Any leakage: {r['any_leakage_count']}\n\n")

            if r["flagged_examples"]:
                f.write("### Flagged Examples\n\n")
                for ex in r["flagged_examples"]:
                    f.write(f"**{ex['target_id']}**: {ex['target_title']}...\n\n")
                    f.write(f"- Title prefix: `{ex['title_prefix']}`\n")
                    f.write(f"- Leakage: {ex['leakage']}\n")
                    f.write(f"- Context preview:\n```\n{ex['context_preview'][:200]}...\n```\n\n")

    print(f"Saved: {md_path}")

    # Final verdict
    print(f"\n=== Verdict ===")
    legacy_status = audit_results["legacy"]["status"]
    clean_status = audit_results["clean"]["status"]
    print(f"Legacy context: {legacy_status}")
    print(f"Clean context: {clean_status}")

    if clean_status == "PASS":
        print("\nClean context PASSES. Safe to proceed with clean-context experiments.")
    else:
        print("\nClean context FAILS. Do not proceed until clean context is fixed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
