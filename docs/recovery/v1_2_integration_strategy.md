# LMCP AutoQuote v1.2 Integration Strategy

Recovered branch `recovered-2026-07-08-clean` is the operational baseline.

Attempted full merge with `origin/release/v1.1` was aborted because histories are unrelated and produced widespread add/add conflicts.

Decision:
- Do not perform wholesale merge.
- Preserve recovered branch as production baseline.
- Selectively port release/v1.1 enterprise features subsystem by subsystem.
- Validate each subsystem independently before promotion.

Priority imports:
1. Tender Knowledge Graph
2. Semantic Retrieval
3. Historical Learning
4. Recommendation Feedback Calibration
5. Governance / Disaster Recovery
6. Executive Intelligence
