# Cross-Model Smoke Test Report

Generated: 2026-06-14

## Configuration

- Provider: SJTU ZhiYuan
- Base URL: https://models.sjtu.edu.cn/api/v1
- Selected model: `glm-5.1`
- Model slug: `glm-51`
- Sleep seconds: 0.5

## Model Inventory

10 models available:

- minimax
- qwen
- glm
- claw
- deepseek-chat
- deepseek-reasoner
- deepseek-v3.2
- minimax-m2.7
- glm-5.1
- qwen3.5-27b

Selected: `glm-5.1` (from `SJTU_MODEL_ID` environment variable)

## Smoke Test Results

| Metric | Value |
|---|---|
| Targets | 3/3 |
| Hits | 2/3 |
| Hit@10 | 66.7% |
| Generation parse rate | 100.0% |
| Judge parse rate | 100.0% |
| Total tokens | 24,192 |
| Target leakage | None |

### Per-Target Results

| Target ID | Title | Ideas | Hit |
|---|---|---:|---|
| 0biUwyjKkm | OpenHOI: Open-World Hand-Object Interaction... | 10 | MISS |
| 1b7whO4SfY | Gated Attention for Large Language Models... | 10 | HIT |
| 4OsgYD7em5 | Does Reinforcement Learning Really Incentivize... | 10 | HIT |

## Go Gate Assessment

| Gate | Status | Details |
|---|---|---|
| Generation parse rate >= 95% | ✅ PASS | 100% |
| Judge parse rate >= 95% | ✅ PASS | 100% |
| No target leakage | ✅ PASS | No target title/contribution in generation prompts |
| No API key in outputs | ✅ PASS | Verified |
| API compatibility | ✅ PASS | OpenAI SDK compatible |

## Security Check

- ✅ No API key written to any file
- ✅ No API key printed in logs
- ✅ No target title or contribution in generation prompts
- ✅ No absolute local paths in output

## Phase 1/2 Readiness

**All gates passed. Phase 1 and Phase 2 are safe to launch.**

The glm-5.1 model:
- Responds quickly (~6-40s per call)
- Returns valid JSON
- Achieves 66.7% Hit@10 on 3 targets (comparable to MiMo's performance)
- No thinking-token issues (unlike MiMo v2.5-pro)

## Recommended Next Steps

1. **Phase 1**: Rejudge existing MiMo final ideas with glm-5.1 judge (77 targets)
2. **Phase 2**: Generate Direct-10 ideas with glm-5.1 generator, judge with MiMo judge (77 targets)

## Output Files

- `results/experiments/20260614_cross_model_zhiyuan1/model_inventory_sjtu_20260614.json`
- `results/experiments/20260614_cross_model_zhiyuan1/smoke_direct10_glm-51_selfjudge_3t_20260614.json`
- `results/experiments/20260614_cross_model_zhiyuan1/smoke_report_20260614.md`
- `results/experiments/20260614_cross_model_zhiyuan1/manifest_20260614.json`
