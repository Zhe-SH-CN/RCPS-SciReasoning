---
type: concept
ingested: 2026-06-02
aliases: [soft-deprecation-kg, auditable-deprecation]
---

# Soft Deprecation

Soft deprecation is a mechanism for retiring outdated facts in knowledge graphs without physical deletion. Instead of removing edges, their status is set to "Deprecated" while retaining associated evidence and timestamps. This preserves historical evolution and enables traceable graph updates.

## Key properties

- **Auditable:** Each deprecation is backed by textual evidence and logged
- **Non-destructive:** Original facts remain in the graph with deprecated status
- **Reversible:** Facts can be re-activated if later evidence supports them
- **Traceable:** Deprecation log records what triggered the retirement

## Implementation in DIAL-KG

DIAL-KG's governance adjudication stage identifies evolutionary events (e.g., discontinuation, replacement) and retrieves targeted outdated facts for soft deprecation. The Deprecation-Handling Precision (D-HP) metric measures how reliably deprecations are textually justified. DIAL-KG achieves D-HP > 0.98 on the SoftRel-∆ dataset.

## Related

- [DIAL-KG](../sources/dial-kg.md): Original paper demonstrating soft deprecation in streaming KGC
- [Incremental KGC](../concepts/incremental-kgc.md): Soft deprecation is a core mechanism for managing knowledge lifecycle
