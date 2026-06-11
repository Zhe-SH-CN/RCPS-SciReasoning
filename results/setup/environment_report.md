# Environment Report

Generated: 2026-06-09

## Python

- **Version:** 3.12.4
- **Location:** /opt/miniconda3/bin/python3.12

## Package Managers

- **uv:** /home/zsz/.local/bin/uv (available)
- **pip:** /opt/miniconda3/bin/pip (available)
- **conda:** /opt/miniconda3/bin/conda (available)

## Virtual Environment

- **Path:** /home/zsz/ICTAI/.venv
- **Created with:** uv venv --python 3.12
- **Installed packages:** datasets, requests, python-dotenv, openai

## Disk Space

- **Filesystem:** /dev/sda
- **Total:** 3.6T
- **Used:** 2.2T
- **Available:** 1.3T (64% used)

## Network

- **MiMo endpoint:** https://token-plan-cn.xiaomimimo.com/v1 (reachable, returns 401 without API key)
- **HF mirror:** https://hf-mirror.com (configured via HF_ENDPOINT env var)

## Environment Variables (.env)

- `XIAOMI_MIMO_BASE_URL`: set
- `XIAOMI_MIMO_API_KEY`: set (redacted)
- `MIMO_MODEL`: mimo-v2.5-pro
- `MIMO_SLEEP_SECONDS`: 0.5
- `HF_ENDPOINT`: https://hf-mirror.com

## Local Data Assets

### Sci-Reasoning Repository

- **Path:** /home/zsz/ICTAI/Sci-Reasoning/
- **prior_work_extraction/results/organized/**: 8 conference-years, 3,451 papers total
  - NeurIPS_2025: 764 files (JSON + MD pairs)
  - NeurIPS_2024: 387 files
  - NeurIPS_2023: 445 files
  - ICLR_2025: 593 files
  - ICLR_2024: 453 files
  - ICML_2025: 319 files
  - ICML_2024: 335 files
  - ICML_2023: 155 files

### Thinking Patterns Classification

- **Path:** /home/zsz/ICTAI/Sci-Reasoning/thinking_patterns_llm_analysis/results/classified_papers.json
- **Records:** 3,291 classified papers
- **NeurIPS 2025 Oral:** 77 papers (exact eval set target)
- **NeurIPS 2025 Spotlight:** 680 papers
- **Fields:** title, conference, year, presentation_type, classification (primary_pattern, secondary_patterns, confidence, reasoning)

### Research Idea Evaluation

- **Path:** /home/zsz/ICTAI/Sci-Reasoning/research_idea_evaluation/
- **Results:** Multiple evaluation result JSONs (GPT-5.2, Claude, Gemini)
- **Code:** Evaluation pipeline scripts

## Key Finding

The classified_papers.json contains exactly 77 NeurIPS 2025 Oral papers, matching the plan's eval set target. The prior_work_extraction organized data has predecessors but uses OpenReview IDs (not paper titles). A join strategy is needed to connect titles to predecessor data.
