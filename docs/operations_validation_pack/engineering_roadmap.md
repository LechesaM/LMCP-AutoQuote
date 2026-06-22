# LMCP Engineering Roadmap

Post-validation programme roadmap tied to the measured failure distribution.

## Baseline

Validated evidence:

- Validation Run 001: READY generation validated
- Validation Run 002: failure distribution measured
- Validation Run 003: delivery, proof capture, and audit traceability validated

Engineering work is driven only by observed Run 002 failures.

## Sprint 1 - Validation and Compliance Hardening

Objective:

Reduce the dominant Run 002 failure class.

Observed failures:

- Missing closing dates
- Missing source/detail URLs
- Document confidence blockers
- Qualification-rule exclusions
- Technical readiness validation blockers

Target deliverables:

- Critical metadata validator
  - Required fields:
    - Closing Date
    - RFQ Number
    - Buyer Name
    - Source URL
    - Submission Method
  - Mandatory field validation
  - Structured missing-field reporting
  - Confidence scoring

- Qualification rule engine
  - Briefing-session exclusions
  - Excluded categories
  - Profit-margin qualification rules
  - Supply-only scope rules
  - Compliance readiness score

- Output states
  - READY
  - REVIEW REQUIRED
  - NOT READY
  - Reason codes for every non-ready outcome

Success metric:

- Reduce Validation failures by at least 50% compared to Run 002.

## Sprint 2 - Document Generation Hardening

Objective:

Reduce document completeness failures.

Observed failures:

- Incomplete schedules
- Missing mandatory submission content
- Incomplete document packs

Target deliverables:

- Submission pack validator
  - Verify existence of:
    - Pricing Schedule
    - Quote Letter
    - Company Documents
    - Supporting Annexures

- Schedule completeness checker
  - Detect empty quantities
  - Detect missing units
  - Detect missing pricing rows
  - Detect incomplete BOQ structures

- Document readiness report
  - Automated pass/fail report before pack release

Success metric:

- Eliminate DOCUMENT_GENERATION failures observed in Run 002.

## Sprint 3 - Extraction Hardening

Objective:

Improve RFQ extraction robustness across varied structures.

Observed failures:

- Metadata extraction failures
- Confidence failures
- RFQ structure variability

Target deliverables:

- Multi-pass extraction
  - Pass 1: field detection
  - Pass 2: validation
  - Pass 3: confidence scoring

- Confidence escalation rules
  - If confidence is below threshold, output REVIEW REQUIRED instead of silent acceptance

- Extraction audit trail
  - Extracted value
  - Source location
  - Confidence score
  - Validation result

Success metric:

- Reduce extraction-related failures to near zero.

## Deferred Work

Not prioritized from the current evidence:

- Supplier network expansion
- BOQ mapping redesign
- Delivery workflow redesign
- Proof-capture redesign
- Audit-trace redesign

Reason:

- Observed failure count for supplier and BOQ mapping was 0.
- Delivery, proof capture, and audit trace were validated in Run 003.

## Sprint 5 - Simulation Gate

Purpose:

Convert the final Sprint 5 simulation run into the formal gate into Sprint 6.

Gate evidence:

- [Sprint 5 Simulation Gate Report](./sprint_5_simulation_gate_report.md)
- Final simulation run: `runtime/simulation_runs/sprint5-20260619T003649Z/`

Gate outcome:

- Lane A behavior preserved
- Lane B behavior preserved
- Lane C behavior preserved
- `lane_d_not_recommended` added for non-qualified, non-rejected records
- `lane_e_edge_cases` remained at `0`
- `approval_gate_bypass_count` remained at `0`
- `duplicate_audit_events` remained at `0`
- `orphaned_audit_events` remained at `0`

Decision:

- Sprint 5 simulation is approved as the governance gate into Sprint 6 audit stress testing.

## Sprint 6 - Audit Stress Testing

Objective:

Validate audit integrity and governance consistency under load.

Launch note:

- [Sprint 6 Launch Note](./sprint_6_launch_note.md)

Test plan:

- [Sprint 6 Test Plan](./sprint_6_test_plan.md)

Operating rules:

- Portal submission: disabled
- Human approval: mandatory
- Approval bypass tolerance: `0`
- Duplicate audit events tolerance: `0`
- Orphaned audit events tolerance: `0`

Success criteria:

- audit events emitted correctly
- no duplicate events
- no orphaned events
- no readiness-state drift
- no approval bypass
- timeline reconstruction accuracy = `100%`

## Validation Exit Criteria

Sprints 1-3 validation exit criteria:

- Conduct Validation Run 004
- Target outcomes:
  - Validation failures materially reduced
  - Document-generation failures materially reduced
  - Extraction failures materially reduced
  - Delivery success remains >= 95%
  - Audit traceability remains 100%

With Sprint 5 complete and approved, LMCP advances into Sprint 6 audit stress testing.

If Sprint 6 succeeds, LMCP can move from simulation-validated into pilot-authorized mode, with manual submission still locked.

## Sprint 7 - Controlled Operational Pilot

Objective:

Validate LMCP performance, governance, and operational usability using live RFQs under controlled conditions.

Pilot documents:

- [Sprint 7 Pilot Plan](./sprint_7_pilot_plan.md)
- [Sprint 7 Execution Log](./sprint_7_execution_log.md)
- [Sprint 7 Dashboard Spec](./sprint_7_dashboard_spec.md)
- [Sprint 7 Results Report](./sprint_7_results_report.md)

Pilot controls:

- Portal submission: disabled
- Human approval: required
- Audit trail: authoritative
- Approval bypass tolerance: `0`
- Duplicate audit event tolerance: `0`
- Orphaned audit event tolerance: `0`
- No workflow shortcuts permitted

Pilot exit target:

- `PILOT PROVEN`
