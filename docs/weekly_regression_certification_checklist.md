# Weekly Regression Certification Checklist

Use this checklist for each controlled proof run.

## Preflight

- [ ] Clean shell
- [ ] `LMCP_RUNTIME_DIR` set correctly
- [ ] Controlled backend boots successfully
- [ ] `GET /health` returns healthy
- [ ] `GET /system/control/effective-status` returns `controlled`
- [ ] `GET /health/workflows` returns `controlled_status: controlled`

## Controlled RFQ Flow

- [ ] Validation passes
- [ ] Quote pack is generated
- [ ] Pricing schedule is generated
- [ ] Submission package is generated

## Safety Controls

- [ ] Portal upload remains disabled
- [ ] Email send remains disabled
- [ ] Autonomous final submit remains disabled

## Comparison

- [ ] Compared against Baseline #1
- [ ] Compared against Baseline #2
- [ ] Compared against Controlled Production Certification
- [ ] No new warnings observed
- [ ] No degraded checks observed

## Decision

- [ ] Approve
- [ ] Reject

## Notes

- Run date:
- RFQ source:
- Runtime directory:
- Proof report path:
- Variance notes:
