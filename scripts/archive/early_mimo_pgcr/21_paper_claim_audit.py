#!/usr/bin/env python3
"""Audit ACML paper claims against local result files.

This script intentionally checks only deterministic local artifacts. It does
not call MiMo or any network service.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "acml_main.tex"
PDF_LOG = ROOT / "paper" / "acml_main.log"
BIB_LOG = ROOT / "paper" / "acml_main.blg"
CHECKLIST = ROOT / "paper" / "acml_submission_checklist.md"
BIB = ROOT / "paper" / "references.bib"
BBL = ROOT / "paper" / "acml_main.bbl"

OUT_JSON = ROOT / "results" / "paper_claim_traceability_audit_2026-06-14.json"
OUT_MD = ROOT / "results" / "paper_claim_traceability_audit_2026-06-14.md"


def load_json(rel: str):
    with (ROOT / rel).open() as f:
        return json.load(f)


def load_jsonl(rel: str):
    with (ROOT / rel).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def read_text(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


def contains_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def main() -> int:
    paper = read_text(PAPER)
    for table_path in sorted((ROOT / "paper" / "tables").glob("*.tex")):
        paper += "\n" + read_text(table_path)
    pdf_log = read_text(PDF_LOG)
    bib_log = read_text(BIB_LOG)
    forbidden_scan_text = paper + "\n" + read_text(BIB) + "\n" + read_text(BBL)

    direct = load_json("results/direct10_complete_mimo_v25pro.json")
    bcs = load_json("results/bcs50_eval_mimo_v25pro.json")
    pgcr = load_json("results/pgcr_enriched_eval.json")
    overlap = load_json("results/rcps_results_audit.json")
    token = load_json("results/token_cost_audit.json")
    selector = load_json("results/selector_failure_audit.json")
    rcps = load_json("results/rcps82_eval_mimo_v25pro.json")
    strict = load_json("results/strict_judge_calibration_10targets.json")
    bcs_candidates = load_jsonl("results/bcs50_candidates_mimo_v25pro.jsonl")
    bcs_selected = load_jsonl("results/bcs50_selected_mimo_v25pro.jsonl")
    pgcr_candidates = load_jsonl("results/pgcr_candidates.jsonl")
    pgcr_selected = load_jsonl("results/pgcr_top10.jsonl")
    enriched_rows = [json.loads(line) for line in (ROOT / "data/scireasoning/eval_neurips_2025_oral_enriched.jsonl").open()]
    bcs_pool_values = [row["total_candidates"] for row in bcs_candidates]
    pgcr_pool_values = [row["total_candidates"] for row in pgcr_candidates]

    claims = [
        {
            "claim": "Direct-10 enriched result",
            "source": "results/direct10_complete_mimo_v25pro.json",
            "expected": {"hits": 20, "total": 77, "hit_at_10": 26.0, "ci": [16.9, 36.4]},
            "source_ok": (
                direct["hits"] == 20
                and direct["total_targets"] == 77
                and direct["hit_at_10"] == 26.0
                and overlap["methods"]["direct10"]["ci"]["low"] == 16.9
                and overlap["methods"]["direct10"]["ci"]["high"] == 36.4
            ),
            "paper_ok": contains_all(paper, ["Direct-10 obtains 20/77", "26.0\\%", "[16.9, 36.4]"]),
        },
        {
            "claim": "Main table pool and final-budget values",
            "source": "results/bcs50_candidates_mimo_v25pro.jsonl; results/bcs50_selected_mimo_v25pro.jsonl; results/pgcr_candidates.jsonl; results/pgcr_top10.jsonl",
            "expected": {
                "direct_pool": 10,
                "direct_final": 10,
                "bcs_pool_min": 20,
                "bcs_pool_max": 50,
                "bcs_final": 10,
                "pgcr_pool_min": 12,
                "pgcr_pool_max": 96,
                "pgcr_final": 10,
            },
            "source_ok": (
                len(direct["targets"]) == 77
                and all(len(row.get("generated_ideas", [])) == 10 for row in direct["targets"])
                and len(bcs_candidates) == 77
                and min(bcs_pool_values) == 20
                and max(bcs_pool_values) == 50
                and len(bcs_selected) == 77
                and all(row.get("selected_count") == 10 for row in bcs_selected)
                and min(pgcr_pool_values) == 12
                and max(pgcr_pool_values) == 96
                and len(pgcr_selected) == 77
                and all(row.get("selected_count") == 10 for row in pgcr_selected)
            ),
            "paper_ok": contains_all(paper, ["Direct-10 & 10 & 10", "BCS-50 & 20--50 & 10", "PGCR & 12--96 & 10"]),
        },
        {
            "claim": "BCS-50 result",
            "source": "results/bcs50_eval_mimo_v25pro.json",
            "expected": {"hits": 16, "total": 77, "hit_at_10": 20.8, "ci": [11.7, 29.9]},
            "source_ok": (
                bcs["hits"] == 16
                and bcs["total_targets"] == 77
                and bcs["hit_at_10"] == 20.8
                and overlap["methods"]["bcs50"]["ci"]["low"] == 11.7
                and overlap["methods"]["bcs50"]["ci"]["high"] == 29.9
            ),
            "paper_ok": contains_all(paper, ["BCS-50 obtains 16/77", "20.8\\%", "[11.7, 29.9]"]),
        },
        {
            "claim": "PGCR enriched result",
            "source": "results/pgcr_enriched_eval.json",
            "expected": {"hits": 14, "total": 77, "hit_at_10": 18.2, "ci": [10.4, 27.3]},
            "source_ok": (
                pgcr["hits"] == 14
                and pgcr["total_targets"] == 77
                and pgcr["hit_at_10"] == 18.2
                and overlap["methods"]["pgcr"]["ci"]["low"] == 10.4
                and overlap["methods"]["pgcr"]["ci"]["high"] == 27.3
            ),
            "paper_ok": contains_all(paper, ["PGCR obtains 14/77", "18.2\\%", "[10.4, 27.3]"]),
        },
        {
            "claim": "BCS/PGCR search forgetting",
            "source": "results/rcps_results_audit.json",
            "expected": {
                "bcs": {"common": 5, "direct_only": 15, "method_only": 11, "net": -4, "union": 31},
                "pgcr": {"common": 3, "direct_only": 17, "method_only": 11, "net": -6, "union": 31},
            },
            "source_ok": (
                overlap["methods"]["bcs50"]["paired_vs_direct10"]["ties"] == 5
                and overlap["methods"]["bcs50"]["paired_vs_direct10"]["losses"] == 15
                and overlap["methods"]["bcs50"]["paired_vs_direct10"]["wins"] == 11
                and overlap["methods"]["direct10"]["hits"] + overlap["methods"]["bcs50"]["paired_vs_direct10"]["wins"] == 31
                and overlap["methods"]["pgcr"]["paired_vs_direct10"]["ties"] == 3
                and overlap["methods"]["pgcr"]["paired_vs_direct10"]["losses"] == 17
                and overlap["methods"]["pgcr"]["paired_vs_direct10"]["wins"] == 11
                and overlap["methods"]["direct10"]["hits"] + overlap["methods"]["pgcr"]["paired_vs_direct10"]["wins"] == 31
            ),
            "paper_ok": contains_all(paper, ["BCS-50 & 5 & 15 & 11 & -4 & 31", "PGCR & 3 & 17 & 11 & -6 & 31"]),
        },
        {
            "claim": "Selector collapse",
            "source": "results/selector_failure_audit.json",
            "expected": {
                "bcs_fallback": 638,
                "bcs_total": 770,
                "bcs_rate": 82.9,
                "pgcr_fallback": 4214,
                "pgcr_total": 4300,
                "pgcr_rate": 98.0,
            },
            "source_ok": (
                selector["bcs"]["fallback_score_3"] == 638
                and selector["bcs"]["total_selected"] == 770
                and selector["bcs"]["fallback_rate"] == 82.9
                and selector["pgcr"]["fallback_score_3"] == 4214
                and selector["pgcr"]["total_scored"] == 4300
                and selector["pgcr"]["fallback_rate"] == 98.0
            ),
            "paper_ok": contains_all(paper, ["638/770", "82.9\\%", "4214/4300", "98.0\\%"]),
        },
        {
            "claim": "Token accounting",
            "source": "results/token_cost_audit.json",
            "expected": {
                "direct_total": 1907440,
                "direct_candidate_processing": 1096918,
                "bcs_total": 4103615,
                "bcs_candidate_processing": 3249927,
                "pgcr_total": 10335016,
                "pgcr_candidate_processing": 9480185,
                "bcs_ratio": 2.15,
                "pgcr_ratio_text": "5.42x",
            },
            "source_ok": (
                token["direct10"]["total"] == 1907440
                and token["direct10"]["generation"] == 1096918
                and token["bcs50"]["total"] == 4103615
                and token["bcs50"]["generation"] + token["bcs50"]["scoring"] == 3249927
                and token["pgcr"]["total"] == 10335016
                and token["pgcr"]["scoring"] == 9480185
                and token["bcs50_vs_direct10_ratio"] == 2.15
            ),
            "paper_ok": contains_all(paper, ["1,096,918", "3,249,927", "9,480,185", "1,907,440", "4,103,615", "10,335,016", "2.15x", "5.42x"]),
        },
        {
            "claim": "Stopped lenient RCPS checkpoint is diagnostic",
            "source": "results/rcps82_eval_mimo_v25pro.json",
            "expected": {"completed": 40, "hits": 40, "parse_ok": 400},
            "source_ok": rcps["completed"] == 40 and rcps["hits"] == 40 and rcps["parse_ok"] == 400,
            "paper_ok": contains_all(paper, ["100\\% \\hitten{}", "zero expansion-only gains", "not a valid improvement"]),
        },
        {
            "claim": "Strict stress sample",
            "source": "results/strict_judge_calibration_10targets.json",
            "expected": {"direct_hits": 0, "rcps_hits": 0, "direct_parse_ok": 100, "rcps_parse_ok": 100},
            "source_ok": (
                strict["method_summaries"]["direct10"]["hits"] == 0
                and strict["method_summaries"]["rcps82"]["hits"] == 0
                and strict["method_summaries"]["direct10"]["parse_ok"] == 100
                and strict["method_summaries"]["rcps82"]["parse_ok"] == 100
            ),
            "paper_ok": contains_all(paper, ["0/10 for both Direct-10 and RCPS-8/2", "stress sample"]),
        },
        {
            "claim": "Enriched eval has 77 non-empty contributions",
            "source": "data/scireasoning/eval_neurips_2025_oral_enriched.jsonl",
            "expected": {"rows": 77, "non_empty_contributions": 77},
            "source_ok": len(enriched_rows) == 77 and sum(bool(r.get("contribution")) for r in enriched_rows) == 77,
            "paper_ok": contains_all(paper, ["77 records were enriched", "non-empty target contributions"]),
        },
    ]

    forbidden_patterns = [
        r"58\.4",
        r"state-of-the-art",
        r"\bSOTA\b",
        r"RCPS improves",
        r"oracle combined",
        r"/home/",
        r"\bzsz\b",
        r"Shanghai",
        r"SJTU",
        r"API key",
        r"secret",
        r"GPT Researcher",
        r"Open Deep Research",
        r"Auto-Research",
        r"gpt-research",
        r"open_deep_research",
        r"assafelovic",
        r"langchain-ai",
        r"2605\.18661",
    ]

    forbidden_hits = []
    for pattern in forbidden_patterns:
        if re.search(pattern, forbidden_scan_text, flags=re.IGNORECASE):
            forbidden_hits.append(pattern)

    log_bad_patterns = [
        "Fatal error",
        "Undefined control sequence",
        "undefined citations",
        "Citation",
        "Warning--empty author",
        "There were undefined",
        "Overfull",
    ]
    log_hits = [pat for pat in log_bad_patterns if pat in pdf_log or pat in bib_log]

    all_claims_ok = all(c["source_ok"] and c["paper_ok"] for c in claims)
    passed = all_claims_ok and not forbidden_hits and not log_hits

    audit = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper": str(PAPER.relative_to(ROOT)),
        "passed": passed,
        "claims": claims,
        "forbidden_hits": forbidden_hits,
        "log_hits": log_hits,
        "notes": [
            "This audit does not verify external citation metadata beyond local BibTeX/log consistency.",
        ],
    }

    OUT_JSON.write_text(json.dumps(audit, indent=2) + "\n")

    lines = [
        "# Paper Claim Traceability Audit",
        "",
        f"Generated: {audit['timestamp']}",
        "",
        f"Verdict: {'PASS' if passed else 'FAIL'}",
        "",
        "## Claim Checks",
        "",
        "| Claim | Source OK | Paper OK | Source |",
        "|---|---:|---:|---|",
    ]
    for c in claims:
        lines.append(
            f"| {c['claim']} | {'yes' if c['source_ok'] else 'no'} | {'yes' if c['paper_ok'] else 'no'} | `{c['source']}` |"
        )
    lines += [
        "",
        "## Forbidden Text Scan",
        "",
        "Forbidden hits: " + (", ".join(f"`{h}`" for h in forbidden_hits) if forbidden_hits else "none"),
        "",
        "## Build Log Scan",
        "",
        "Problematic log hits: " + (", ".join(f"`{h}`" for h in log_hits) if log_hits else "none"),
        "",
        "## Notes",
        "",
    ]
    for note in audit["notes"]:
        lines.append(f"- {note}")
    OUT_MD.write_text("\n".join(lines) + "\n")

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
