# Real RFQ Manual Pilot Execution

This workflow is for a controlled assisted-production pilot using 3 to 5 real RFQs.

Guardrails
- Use the canonical `TenderSubmissionPipeline`.
- Run every RFQ with `mode="assisted_production"`.
- Run every RFQ with `dry_run=true` only.
- Keep `require_human_approval=true`.
- Do not attempt final submission from this pilot workflow.
- Do not enable autonomous submission.

Recommended Pilot Scope
1. Select 3 to 5 real RFQs that are likely supply-and-delivery tenders.
2. Exclude tenders that are obviously blocked before the run when possible:
   - medical consumables
   - IT equipment
   - petrol/diesel
   - catering
   - compulsory briefing/session tenders
3. Store each tender pack in its own folder on disk.

Preflight
1. Run `GET /go-live/readiness`.
2. Confirm `overall_status` is not `blocked`.
3. Review `/go-live/pilot-runs/report` if prior pilot runs already exist.

If you are running locally and the database is unavailable, start the API in degraded mode for pilot review only:

```bash
export LMCP_ALLOW_DEGRADED_STARTUP=true
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

CLI Workflow
Use the helper script once per real RFQ:

```bash
python3 scripts/run_manual_pilot.py \
  --tender-root /absolute/path/to/tender-pack \
  --tender-id REAL-RFQ-001
```

Optional instructions text can be passed explicitly:

```bash
python3 scripts/run_manual_pilot.py \
  --tender-root /absolute/path/to/tender-pack \
  --tender-id REAL-RFQ-002 \
  --instructions-text "Supply and delivery of office furniture. No compulsory briefing."
```

Expected Script Behavior
- Calls the canonical `TenderSubmissionPipeline` directly.
- Forces:
  - `mode="assisted_production"`
  - `dry_run=true`
  - `require_human_approval=true`
- Never attempts final submission.
- Prints:
  - status
  - detected category
  - excluded/not excluded
  - mandatory forms detected
  - quote pack generated
  - submission pack generated
  - warnings/errors
  - pilot log location

When a pack is approval-ready, record manual approval without submitting:

```bash
python3 scripts/approve_manual_pilot.py \
  --tender-root /absolute/path/to/tender-pack \
  --tender-id REAL-RFQ-003 \
  --pricing-file /absolute/path/to/pricing.json \
  --confirm-approval
```

The approval command refuses unless the pack is `approval_ready`, unblocked, has no unmatched pricing rows, has no warnings, and has not attempted final submission.

After approval, run the final review command before any submission work:

```bash
python3 scripts/review_submission_pack.py \
  --tender-root /absolute/path/to/tender-pack \
  --tender-id REAL-RFQ-003
```

The review command only records a review audit; it does not submit anything.

If the submission was completed manually outside automation, capture proof after the fact:

```bash
python3 scripts/record_manual_submission_proof.py \
  --tender-id REAL-RFQ-003 \
  --tender-root /absolute/path/to/tender-pack \
  --portal-name eTenders \
  --submission-reference SUB-10001 \
  --submitted-by "Manual Operator"
```

This only records proof metadata and never submits through the automation stack.

Operator Review Steps Per RFQ
1. Confirm the result status is either:
   - `pending_human_approval`
   - `blocked`
2. Review detected category and excluded status.
3. Review mandatory forms detected.
4. Review generated quote pack and submission pack outputs.
5. Confirm there was no final submission attempt.
6. Save the audit and pilot log references for the run.

After 3 To 5 RFQs
1. Open `GET /go-live/pilot-runs`.
2. Open `GET /go-live/pilot-runs/report`.
3. Review:
   - blocked vs non-blocked mix
   - common warnings
   - common errors
   - excluded categories found
   - frequently detected mandatory forms
   - readiness recommendation

Offline Usage
If the API cannot bind a port, print the same pilot report directly from the JSONL log:

```bash
python3 scripts/show_manual_pilot_report.py \
  --log-path runtime/manual_production/pilot_runs.jsonl
```

Use `--limit` to narrow the report to the most recent runs.

To start the local backend and frontend together for operator review:

```bash
bash scripts/start_local_manual_production.sh
```

To verify the current local system state after launch:

```bash
python3 scripts/check_local_system.py
```

Controlled shared-runtime proof
If you want a one-command local proof of the controlled runtime path, use:

```bash
make controlled-proof
```

That wrapper will:
- seed `LMCP_RUNTIME_DIR` with a controlled policy and RFQ record
- start the backend
- verify:
  - `GET /health`
  - `GET /system/control/effective-status`
  - `GET /health/workflows`
- run the controlled RFQ chain:
  - validate
  - quote pack
  - buyer pricing schedule
  - submission package

It keeps the safety gates in place:
- no portal upload
- no email send
- no autonomous final submit

If your sandbox blocks binding on `127.0.0.1:8000`, the wrapper uses port `8011` by default in this environment.

Exit Criteria
- Manual production remains dry-run only.
- Human approval remains required.
- No final submission occurs from this workflow.
- Pilot evidence is captured in the pilot run log and audit outputs.
