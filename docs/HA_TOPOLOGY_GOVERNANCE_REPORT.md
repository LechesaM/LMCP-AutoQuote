# HA Topology Governance Report

## Scope
Read-only staging governance for the LMCP AutoQuote high-availability topology scaffold.

## Evidence Sources
- `k8s/base/`
- `k8s/overlays/staging/`
- `k8s/overlays/production/`
- Staged production operationalization and supervision governance snapshots

## Exposed Routes
- `GET /rfq-lifecycle/ha-topology`
- `GET /rfq-lifecycle/ha-topology/latest`
- `GET /rfq-lifecycle/ha-topology/history`

## Tracked Signals
- Redis HA readiness
- PostgreSQL replication readiness
- Quorum readiness
- Failover orchestration readiness
- Persistence durability readiness
- Replica supervision readiness
- Split-brain prevention readiness
- HA degradation indicators
- HA governance history

## Command Centre Panel
- `Command Centre HA topology panel`

## Operating Constraints
- read-only
- staging-only
- dry-run enforced
- supervision mandatory
- no live authority
- no autonomous submissions
- no production credentials
