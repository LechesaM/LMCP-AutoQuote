# Validation Run 002

Coverage validation against the frozen baseline.

## Run Metadata

- Run ID: `VALIDATION_RUN_002`
- Baseline: `validated-baseline-v1`
- Baseline Commit: `f5cadbd`
- Objective: category diversity validation
- Target RFQs: `20`

## Scope

- Office Supplies: `3`
- PPE: `3`
- Cleaning Materials: `3`
- Electrical Materials: `3`
- Plumbing Materials: `3`
- Building Materials: `3`
- General Hardware: `2`

## Additional Capture Field

- `Reason_For_Manual_Approval`

## Allowed Values

- `GOVERNANCE_REVIEW`
- `PRICING_REVIEW`
- `SUPPLIER_REVIEW`
- `COMPLIANCE_REVIEW`
- `RISK_REVIEW`
- `TECHNICAL_LIMITATION`
- `OTHER`

## Success Criteria

- `20` RFQs processed
- Submission ready rate `>= 90%`
- Approval reason capture `100%`
- Failure classification `100%`
- Audit traceability `100%`

## Operating Rule

- Use the frozen baseline only.
- Do not change workflow, approval, qualification, pack generation, or submission logic.
- Capture the reason for manual approval on every RFQ.
- Review after the first `5` RFQs, then continue to `20`.

## First Batch

- RFQ-001-R2: `RFQ-MESSY-001` / Office Supplies
- RFQ-002-R2: `RFQ-MISSING-001` / Cleaning Materials
- RFQ-003-R2: `PILOT-005-E2E-20260528` / PPE
- RFQ-004-R2: `RFQ_005` / Building Materials
- RFQ-005-R2: `RFQ_004` / General Hardware

## Execution Note

- The first batch was populated from the current evidence inventory.
- Exact electrical and plumbing fixtures were not present in the current inventory, so the closest governed hardware-style record was used for the fifth slot.
- `Reason_For_Manual_Approval` is captured on every Run 002 record and is expected to remain `GOVERNANCE_REVIEW` unless the evidence shows otherwise.

## Notes

- Validation Run 002 starts from `validated-baseline-v1`.
- The purpose is category diversity coverage, not submission validation.
- This record is the lightweight parent control document for Run 002.

## Midpoint Review

- RFQs processed: `10/20`
- Ready: `6`
- Not ready: `4`
- Approval reasons observed: `GOVERNANCE_REVIEW`, `PRICING_REVIEW`
- Failure classes observed: `EXTRACTION`, `DOCUMENT_GENERATION`, `VALIDATION`, `PRICING`
- Supplier failures observed: `0`
- BOQ mapping failures observed: `0`
- The midpoint confirms the frozen baseline remains stable across mixed evidence, while pricing and validation-related issues continue to dominate the diversified sample.

## Closeout

- Status: `COMPLETED`
- Completed on: `2026-06-18`
- RFQs processed: `20/20`
- Ready: `9`
- Not ready: `11`
- Approval reasons observed: `GOVERNANCE_REVIEW`, `COMPLIANCE_REVIEW`, `PRICING_REVIEW`
- Failure classes observed: `VALIDATION`, `DOCUMENT_GENERATION`, `PRICING`, `EXTRACTION`
- Supplier failures observed: `0`
- BOQ mapping failures observed: `0`
- Final evidence frozen in `docs/operations_validation_pack/validation_run_002_report.md`
