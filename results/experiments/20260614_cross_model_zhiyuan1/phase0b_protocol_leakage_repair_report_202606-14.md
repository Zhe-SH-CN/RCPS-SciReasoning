# Phase 0b Protocol Leakage Repair Report

Generated: 2026-06-14

## Summary

| Check | Status |
|---|---|
| Legacy context leakage audit | FAIL |
| Clean context leakage audit | PASS |
| Clean smoke generation parse rate | 100.0% |
| Clean smoke judge parse rate | 100.0% |
| Clean smoke targets completed | 3/3 |
| Clean smoke hits | 0/3 |
| API key in outputs | None |
| Target leakage in generation | None |

**Phase 0b verdict: PASS**

## 1. Offline Leakage Audit

### Legacy Context (FAIL)

Uses: predecessor title, role, relationship_sentence, synthesis_narrative

| Metric | Count |
|---|---:|
| Total targets | 77 |
| Exact title matches | 5/77 |
| Exact contribution matches | 0/77 |
| Title prefix matches | 23/77 |
| Any leakage | 28/77 |

Unsafe fields: `synthesis_narrative`, `predecessor.role`, `predecessor.relationship_sentence`

### Clean Context (PASS)

Uses: predecessor titles only

| Metric | Count |
|---|---:|
| Total targets | 77 |
| Exact title matches | 0/77 |
| Exact contribution matches | 0/77 |
| Title prefix matches | 0/77 |
| Any leakage | 0/77 |

Unsafe fields: none

## 2. Clean-Context Smoke Test

### Configuration

- Model: `glm-5.1`
- Context mode: clean (predecessor titles only)
- Targets: 3 (first 3 from enriched eval data)

### Results

| Metric | Value |
|---|---|
| Completed | 3/3 |
| Hits | 0/3 |
| Hit@10 | 0.0% |
| Generation parse rate | 100.0% |
| Judge parse rate | 100.0% |
| Total tokens | 21,750 |

### Per-Target Results

| Target ID | Ideas | Hit |
|---|---:|---|
| 0biUwyjKkm | 10 | MISS |
| 1b7whO4SfY | 10 | MISS |
| 4OsgYD7em5 | 10 | MISS |

### Parser Fix

The initial smoke test had a 66.7% generation parse rate due to trailing commas in the API's JSON output. Fixed by adding trailing comma removal to the parser:
```python
text = re.sub(r",\s*\]", "]", text)
text = re.sub(r",\s*\}", "}", text)
```

After the fix: 100% parse rate on all 3 targets.

## 3. Security Check

- ✅ No API key written to any file
- ✅ No API key printed in logs
- ✅ No target title or contribution in generation prompts
- ✅ No synthesis_narrative in generation prompts
- ✅ No predecessor role in generation prompts
- ✅ No predecessor relationship_sentence in generation prompts

## 4. Go/No-Go Assessment

| Criterion | Status |
|---|---|
| Legacy context flagged as leaking/unsafe | ✅ PASS |
| Clean context uses only predecessor titles | ✅ PASS |
| Clean context has zero exact target matches | ✅ PASS |
| Clean smoke completes 3/3 targets | ✅ PASS |
| Clean smoke has exactly 10 parsed ideas per target | ✅ PASS |
| Clean smoke judge parse rate >= 95% | ✅ PASS |
| No API key material in outputs/logs | ✅ PASS |

**All criteria passed. Phase 0b is PASS.**

## 5. Recommendation

Codex should consider a full clean Direct-10 run on all 77 targets. The clean context:
- Eliminates all target-derived bridge text
- Achieves 100% parse rate
- Produces exactly 10 ideas per target

However, the 0/3 hit rate on the smoke test suggests that clean-context generation may produce fewer hits than the legacy context. This is expected and should be measured properly on the full 77-target set.

## Output Files

- `results/prompt_context_leakage_audit_2026-06-14.json`
- `results/prompt_context_leakage_audit_2026-06-14.md`
- `results/experiments/20260614_cross_model_zhiyuan1/smoke_direct10_glm-51_selfjudge_cleanctx_3t_20260614.json`
- `results/experiments/20260614_cross_model_zhiyuan1/phase0b_protocol_leakage_repair_report_20260614.md`
- `results/experiments/20260614_cross_model_zhiyuan1/manifest_20260614.json`
