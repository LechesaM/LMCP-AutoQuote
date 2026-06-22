# Sprint 5 Simulation Gate Report

## Scope

This report is generated from the final Sprint 5 simulation run at `runtime/simulation_runs/sprint5-20260619T003649Z/`.

Source artifacts:

- `simulation_manifest.json`
- `simulation_results.json`
- `simulation_metrics.json`
- `simulation_lane_metrics.json`
- `simulation_audit.json`

## Gate Decision

Sprint 5 passes the simulation gate and is approved to move into Sprint 6: audit stress testing.

The run shows stable Lane A, B, and C behavior, a clean split of the previously non-qualified population into the new `lane_d_not_recommended` bucket, and no residual edge-case leakage.

## Executive Summary

| KPI | Value |
| --- | ---: |
| RFQs requested | 100 |
| RFQs selected | 100 |
| RFQs harvested | 100 |
| Qualified | 49 |
| Rejected | 51 |
| Submission packs generated | 49 |
| Submission packs blocked | 17 |
| Submission packs approved | 0 |
| Qualification success rate | 49.0% |
| Qualification reject rate | 51.0% |
| Qualification accuracy | 92.0% |
| Submission pack success rate | 65.31% |
| Submission pack block rate | 34.69% |
| Average readiness score | 95.84 |

## Lane Model Outcome

| Lane | Count | Interpretation |
| --- | ---: | --- |
| `lane_a_eligible_complete` | 32 | Qualified, approval-ready, and unblocked |
| `lane_b_eligible_blocked` | 17 | Qualified, but blocked by missing documents |
| `lane_c_rejected` | 34 | Explicitly rejected through qualification rules |
| `lane_d_not_recommended` | 17 | Non-qualified records that were not explicitly rejected |
| `lane_e_edge_cases` | 0 | Residual fallback bucket; should remain empty |

The `lane_d_not_recommended` population is entirely composed of below-margin records from the historical and pilot corpora:

- `RFQ-BELOW-001`: 9
- `REAL-PILOT-005`: 8

## Audit Gate Checks

| Check | Value |
| --- | ---: |
| `approval_gate_bypass_count` | 0 |
| `submission_ready_without_approval_count` | 0 |
| `audit_events_missing` | 0 |
| `duplicate_audit_events` | 0 |
| `orphaned_audit_events` | 0 |
| `audit_integrity_failures` | 0 |

These values show the simulation preserved the approval gate and did not introduce audit duplication or orphaning.

## Gate Rationale

Sprint 5 is complete enough to freeze and hand off because:

1. The lane model now separates explicit rejection from non-recommended, non-rejected records.
2. Lane A, B, and C behavior remains intact.
3. The fallback `lane_e_edge_cases` bucket is empty.
4. Audit controls remain clean at the run level.
5. The run is internally consistent across results, metrics, lane metrics, and audit outputs.

## Sprint 6 Focus

Sprint 6 should use this gate as the baseline for audit stress testing, with emphasis on:

- high-volume audit event emission
- duplicate-event detection
- orphan-event detection
- approval-gate bypass resistance
- integrity checks under repeated and mixed-path simulation load

## Conclusion

Sprint 5 simulation evidence supports promotion to Sprint 6: audit stress testing.

The gate condition is satisfied by the final run in `runtime/simulation_runs/sprint5-20260619T003649Z/`, and the residual edge-case bucket is zero.
