# ACML 2026 Submission Checklist

## Venue

- [ ] Target is ACML 2026 Conference Track.
- [ ] Submission deadline checked: 2026-06-26, 23:59 AoE.
- [ ] Reviewer nomination requirement handled or PC exception requested before 2026-06-23.
- [ ] OpenReview submission metadata prepared.

## Format

- [ ] Uses `ACML_camera_ready/acml26_submission_template.tex`.
- [ ] Uses ACML/JMLR style, not IEEE.
- [ ] Author fields left empty for double-blind review.
- [ ] No SJTU, local path, username, repository URL, API key, or self-identifying text.
- [ ] Fits 16 pages including references and appendix.
- [ ] PDF compiles without missing references or overfull layout problems.

## Evidence

- [ ] `data/scireasoning/eval_neurips_2025_oral_enriched.jsonl` has 77 non-empty contributions.
- [ ] Every reported number is generated from JSON/JSONL outputs, not markdown summaries.
- [ ] The 58.4% oracle combined result is not reported as the main method.
- [ ] PGCR is reported as a negative ablation unless corrected experiments change the conclusion.
- [ ] Main BCS result is full-set, oracle-free, exactly 10 final ideas per target.
- [ ] Judge robustness or cross-model replication is included.
- [ ] Bootstrap confidence intervals or paired comparisons are reported.

## Paper

- [ ] Title and abstract match the corrected BCS framing.
- [ ] Related work citations are real and verified.
- [ ] Method section makes target-hidden selection explicit.
- [ ] Limitations mention judge dependence, title/contribution quality, token cost, and single-benchmark scope.
- [ ] Appendix includes prompts, data construction, and enough implementation detail to reproduce.

## Stop Conditions

- [ ] If full-set BCS does not beat direct baseline, do not write an improvement claim.
- [ ] If enriched judging reverses the result, update the framing honestly.
- [ ] If the paper cannot compile cleanly by 2026-06-24, stop experiments and focus on paper stabilization.

