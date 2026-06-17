# Internal Launch Runbook

## Deployment Sequence

1. Validate environment variables and runtime directories.
2. Confirm auth/RBAC configuration.
3. Verify backend startup.
4. Verify frontend production build.
5. Confirm Docker images build successfully.
6. Apply nginx reverse proxy configuration.
7. Start backend services.
8. Start frontend services.
9. Verify telemetry endpoints.
10. Verify governance controls.
11. Launch supervised-live operator workflows.

## Controlled MVP Pilot

Use this after the hardening sprint is complete and before any broader launch.

### Pilot Scope

- Run one real supply-and-delivery RFQ end to end first.
- Then run a small batch of 5-10 real RFQs under human approval.
- Do not enable autonomous final submission.
- Keep benchmark gates, eTenders preflight, and production guardrails unchanged.

### Exact Flow

1. Harvest the RFQ.
2. Persist it to the live store.
3. Extract and normalize the documents.
4. Apply the eligibility gate.
5. Run pricing.
6. Generate the quote pack.
7. Record operator approval.
8. Submit through the buyer channel manually or under assisted automation.
9. Capture proof immediately.
10. Persist the proof record in submission history.

### Proof-Chain Fields

The submission history record must include:

- `proof_path`
- `submission_channel`
- `buyer_confirmation_reference`
- `receipt_text`
- `receipt_timestamp`
- `submitted_files`

### Pilot Success Criteria

- The RFQ reaches `submission` and `proof record` without hidden manual repair.
- The proof-chain fields above are present in submission history.
- Any rejection reason is explicit and attributable.
- Manual approval remains required before final submission.
- No autonomous approval or autonomous final submission occurs.

## Pilot Stages

### Stage 1 - Controlled Pilot

Run `5` RFQs, then `10`, then `25`.

Track:

| Metric | Target |
| --- | --- |
| RFQ harvested | `100%` |
| RFQ persisted | `100%` |
| RFQ correctly classified | `>95%` |
| Eligible RFQs correctly selected | `>95%` |
| Quote packs generated | `>95%` |
| Submission proof recorded | `100%` |
| Human intervention rate | decreasing |

### Stage 2 - Pilot Dashboard

The operational dashboard must show:

- RFQs Harvested
- RFQs Rejected
- RFQs Approved
- Quote Packs Generated
- Submission Records
- Proof Records
- Pilot Success Rate

### Stage 3 - Production Candidate

After `25-50` successful RFQs with:

- no persistence failures
- no proof-chain failures
- no submission-history failures

the release can be treated as a production candidate.

### Stage 4 - Autonomous Expansion

Only after production candidate validation:

- expand supplier intelligence automation
- expand procurement intelligence loops
- expand award intelligence
- expand autonomous opportunity prioritisation

Keep human approval required until sufficient pilot evidence exists.

## Rollback Procedure

1. Stop supervised-live traffic.
2. Preserve runtime and audit artifacts.
3. Restore the previous deployment image or tag.
4. Re-run backend and frontend validation.
5. Re-confirm manual-only governance before resuming.

## Verification Points

- backend startup
- frontend startup
- docker deployment
- auth setup
- telemetry checks
- governance verification
- incident escalation readiness
