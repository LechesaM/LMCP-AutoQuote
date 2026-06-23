# Procurement Intelligence Governance

## Scope
This stage 7B governance layer provides read-only operational intelligence across supervised procurement operations. It does not grant autonomous procurement authority and does not modify workflow behavior.

## Governance Dimensions
- RFQ trend analysis
- submission modality utilization analysis
- operational bottleneck analysis
- compliance drift analysis
- governance anomaly analysis
- supervision-load analysis
- recurring blocker analysis
- operational throughput analysis

## Intelligence Outputs
- operational intelligence scoring
- governance degradation indicators
- anomaly severity indicators
- supervision saturation indicators
- operational optimization indicators
- intelligence governance history

## Runtime Surface
The operational intelligence surface is staged through:
- `GET /rfq-lifecycle/operational-intelligence`
- `GET /rfq-lifecycle/operational-intelligence/latest`
- `GET /rfq-lifecycle/operational-intelligence/history`

The Command Centre exposes a read-only operational intelligence panel backed by the same staging data sources used by the rest of the controlled governance surface.

## Data Sources
- `runtime/staging/pilot-cycles/`
- `runtime/staging/evidence-packs/`
- existing RFQ lifecycle analytics and telemetry snapshots
- supervised pilot, review-board, and readiness governance summaries

## Constraints
- No autonomous procurement authority
- No irreversible actions
- No production connectivity requirement
- Dry-run protections remain active
- Governance and human supervision remain authoritative
