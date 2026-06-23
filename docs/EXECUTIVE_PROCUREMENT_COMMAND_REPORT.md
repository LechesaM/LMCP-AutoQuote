# Executive Procurement Command Governance

## Purpose
This governance layer provides read-only executive command visibility over supervised procurement operations. It does not grant autonomous procurement authority and does not alter workflow behavior.

## Covered Analyses
- procurement throughput forecasting
- operational risk forecasting
- governance degradation forecasting
- supervision-capacity forecasting
- procurement health scoring
- procurement trend forecasting
- escalation forecasting
- strategic procurement summaries

## Outputs
- executive governance scoring
- institutional-risk indicators
- procurement saturation indicators
- strategic readiness indicators
- operational forecasting indicators
- executive intelligence history

## Runtime Surface
The executive command surface is staged through:
- `GET /rfq-lifecycle/executive-command`
- `GET /rfq-lifecycle/executive-command/latest`
- `GET /rfq-lifecycle/executive-command/history`

The Command Centre exposes a read-only executive-command panel backed by the same staging data sources used by the controlled governance surface.

## Data Sources
- `runtime/staging/pilot-cycles/`
- `runtime/staging/evidence-packs/`
- current RFQ lifecycle analytics and telemetry
- operational intelligence, final readiness, stability, review-board, and operational pilot execution snapshots

## Constraints
- No autonomous procurement authority
- No irreversible actions
- No production connectivity requirement
- Dry-run protections remain active
- Governance and human supervision remain authoritative
