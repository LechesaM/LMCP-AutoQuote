# Weekly Regression Run #2 Checklist

Use this checklist when a valid trigger occurs and the second regression run is executed.

## Run Context

- Milestone: `Weekly Regression Run #2`
- State before run: `repository frozen`
- Change policy before run: `no workflow changes`
- Execution mode: `controlled`

## Comparison Set

- Baseline #1
- Baseline #2
- Controlled Production Certification (`2cfa3ae7`)
- Weekly Regression Run #1 (`cc31c532`)

## Success Criteria

- [ ] Controlled status remains `controlled`
- [ ] Health remains `healthy`
- [ ] Workflow checks remain `7 / 7`
- [ ] Quote pack is generated
- [ ] Pricing schedule is generated
- [ ] Submission package is generated
- [ ] Safety controls remain blocked as intended
- [ ] No new warnings appear
- [ ] No degraded checks appear
- [ ] Variance remains `none` or is explicitly explained and approved

## Required Evidence

- [ ] `GET /health`
- [ ] `GET /system/control/effective-status`
- [ ] `GET /health/workflows`
- [ ] Controlled proof report
- [ ] Quote pack artifact path
- [ ] Pricing schedule artifact paths
- [ ] Submission manifest path

## Decision Rule

- Approve if the run matches the certified controlled workflow envelope and no new regressions appear.
- Reject if controlled status changes, any workflow check degrades, or any safety control is weakened.

## Notes

- Trigger used:
- RFQ source:
- Runtime directory:
- Proof log:
- Endpoint log:
- Report log:
- Variance notes:

