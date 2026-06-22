# Failure Log

Track every blocker, root cause, and fix during operations validation.

## Fields

| Failure ID | RFQ ID | Stage | Date | Description | Root Cause | Fix Applied | Regression Test Added | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

## Logging Rules

- Create one log entry per failure event.
- Capture the first observable stage where the failure occurred.
- Document the root cause before applying a fix.
- Add a regression test before closing the item.
- Keep ownership explicit.
- Mark status only after the failure is resolved or accepted.

## RFQ-001

- No failure recorded.
- Manual approval was required and completed.

## RFQ-002

- No failure recorded.
- Manual approval was required and completed.

## RFQ-003

- No failure recorded.
- Manual approval was required and completed.

## RFQ-004

- No failure recorded.
- Manual approval was required and completed.

## RFQ-005

- No failure recorded.
- Manual approval was required and completed.

## RFQ-006

- No failure recorded.
- Manual approval was required and completed.

## RFQ-007

- No failure recorded.
- Manual approval was required and completed.

## RFQ-008

- No failure recorded.
- Manual approval was required and completed.

## RFQ-009

- No failure recorded.
- Manual approval was required and completed.

## RFQ-010

- No failure recorded.
- Manual approval was required and completed.

## Validation Run 002 Batch 1

- RFQ-001-R2: no blocking failure recorded; fixture is intentionally sparse and remains not submission-ready.
- RFQ-002-R2: no blocking failure recorded; the source-document gap is the observed issue in the fixture.
- RFQ-003-R2: no blocking failure recorded; the PPE archive record remains rejected for missing documentation and closing-date evidence.
- RFQ-004-R2: no failure recorded; manual approval was required and completed in the governed baseline record.
- RFQ-005-R2: no failure recorded; manual approval was required and completed in the governed baseline record.

## Validation Run 002 RFQ-006

- RFQ-006-R2: pricing below threshold; minimum profit R30,000 not met and minimum supply margin 25% not met.

## Validation Run 002 RFQ-007

- RFQ-007-R2: no blocking failure recorded; ready governed fixture with review-ready and proof-recorded evidence.

## Validation Run 002 RFQ-008

- RFQ-008-R2: no blocking failure recorded; ready governed E2E fixture with submission pack and proof-recorded evidence.

## Validation Run 002 RFQ-009

- RFQ-009-R2: no blocking failure recorded; ready governed office-consumables fixture with quote pack and submission manifest present.

## Validation Run 002 RFQ-010

- RFQ-010-R2: no blocking failure recorded; ready governed office-consumables fixture from the RFQ fixture set.

## Validation Run 002 RFQ-011

- RFQ-011-R2: lifecycle rejection for missing closing date and document-confidence blockers on the live cleaning-materials record.

## Validation Run 002 RFQ-012

- RFQ-012-R2: no blocking failure recorded; ready governed facility-maintenance record from the archived E2E set.

## Validation Run 002 RFQ-013

- RFQ-013-R2: lifecycle rejection for missing closing date and document-processing blockers on the live office-supplies record.

## Validation Run 002 RFQ-014

- RFQ-014-R2: lifecycle rejection for missing source/detail URL, closing date, and document-confidence blockers on the live office-supplies record.

## Validation Run 002 RFQ-015

- RFQ-015-R2: no blocking failure recorded; ready governed store-replenishment fixture from the evidence inventory.

## Validation Run 002 RFQ-016

- RFQ-016-R2: excluded briefing-session fixture; non-qualifying opportunity blocked before readiness.

## Validation Run 002 RFQ-017

- RFQ-017-R2: incomplete schedule detail prevented readiness on the eligible supply-and-delivery fixture.

## Validation Run 002 RFQ-018

- RFQ-018-R2: below-margin pricing prevented readiness on the eligible supply-and-delivery fixture.

## Validation Run 002 RFQ-019

- RFQ-019-R2: technical validation requirement keeps the high-confidence fixture out of the current readiness set.

## Validation Run 002 RFQ-020

- RFQ-020-R2: no blocking failure recorded; ready governed household-products fixture from the qualification set.

## Validation Run 004 Summary

- Full Run 004 sample measured against the Sprint 1 baseline.
- Validation failures remained at 6, so the Sprint 1 target was not met.
- Document-generation, pricing, and extraction remained bounded in the measured sample.
- Supplier and BOQ mapping did not emerge as blockers in the run.

## Validation Run 005 First Review

- First Run 005 slice measured against the Sprint 1.1 baseline.
- Metadata-completeness blockers remain visible in the failing rows.
- The first slice does not yet show the target reduction in metadata-completeness failures.
- Supplier and BOQ mapping remain absent as blockers in the reviewed slice.

## Validation Run 005 Midpoint

- Run 005 reached the 10/20 checkpoint with the second five-row slice still entirely not ready.
- Metadata-completeness blockers remained visible in all five new rows.
- RFQ-006-R5 also carried a qualification-exclusion subtype, but the dominant surviving issue remained metadata completeness.
- The midpoint does not yet show a reduction below the Run 004 baseline, so the run should continue to RFQ-020-R5 before a remediation decision is made.

## Validation Run 005 Closeout

- Run 005 closed with `2 READY` and `18 NOT READY` across the full sample.
- Metadata-completeness blockers remained the dominant issue at the end of the run.
- Qualification-exclusion and technical-validation cases remained distinct but did not displace metadata completeness as the primary blocker.
- No delivery or audit-trace regression was observed during the re-measurement pass.

## Validation Run 006 Midpoint

- The first 10 executable live-queue records currently available in `runtime/live_rfqs.json` were measured as the Run 006 midpoint evidence set.
- Midpoint result: `0 READY` and `10 NOT READY`.
- Metadata-completeness blockers remain visible, with document-confidence and missing-document issue codes recurring in the live queue.
- Qualification exclusions remain distinct from metadata-completeness failures.
- No delivery or audit-trace regressions were introduced by Sprint 1.2 in the measured midpoint queue.

## Validation Run 006 Closeout

- The live evidence store exposes `15` executable RFQs, not the full planned `20`.
- The missing five records cannot be recovered from the current evidence store without inventing data.
- The run was re-baselined as a `15-RFQ Live Queue Benchmark` and closed on the evidence that exists.
- Final benchmark result: `0 READY` and `15 NOT READY`.
- Metadata-completeness remained the dominant blocker, with document-generation and extraction gaps still present in the live queue.

## Validation Run 007 Completion

- Run 007 measured the same live-queue benchmark after Sprint 1.3 metadata recovery hardening.
- Final benchmark result: `2 READY` and `13 NOT READY`.
- `FIN-SCM-TEN-0236` and `FIN-SCM-TEN-0235` converted to READY after recovered closing-date and source/detail URL evidence was applied.
- The live queue still shows dominant metadata-completeness issues, but recovery now changes outcomes in the positive direction.

## Validation Run 008 Completion

- Run 008 measured the live queue after Sprint 2 document-generation hardening.
- Final benchmark result: `0 READY` and `15 NOT READY`.
- Three records generated quote-pack evidence, pricing schedules, returnables, and BOQ detection, but those records remained not-ready because of qualification or expiry conditions.
- Document-generation, extraction, and metadata-completeness blockers remain present in the live queue.
- No delivery or audit-trace regressions were observed.

## Validation Run 008 Failure Attribution

- The 15 not-ready records were attributed primarily to:
  - `business-rule exclusion`: 6
  - `qualification exclusion`: 4
  - `expired RFQ`: 4
  - `missing source data`: 1
- Document-generation blockers were present as secondary signals, but they did not explain the primary READY failure in this benchmark.
