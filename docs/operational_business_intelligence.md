# Operational Business Intelligence

LMCP operational business intelligence turns live runtime data into executive-facing analytics without changing procurement behavior.

## Architecture

- Runtime telemetry, workflow summaries, queue data, operator actions, source health, pricing evidence and supervised-live readiness feed the BI layer.
- The BI layer is read-only.
- Forecasts are advisory only.
- Export paths are sanitized and do not include secrets, tokens or credentials.

## KPI Strategy

- Focus on RFQs harvested, qualified, reviewed and governed.
- Track estimated profitability instead of accounting data.
- Track source ROI, governance trends and workload pressure.
- Keep all recommendation outputs human-reviewed.

## Governance Protections

- Manual approval remains mandatory.
- `review_ready` remains mandatory.
- Proof capture remains mandatory.
- Final submission remains manual-only.

