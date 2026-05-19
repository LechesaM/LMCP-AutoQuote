# Failure Recovery SOP

## DB Unavailable

- Keep the workflow operating in JSONL compatibility mode
- Report the persistence failure
- Retry after the runtime issue is cleared

## JSONL Corruption

- Stop and isolate the corrupted log file
- Restore from the latest safe copy if available
- Refuse new work until workflow history is trustworthy again

## Missing Runtime Directories

- Recreate the required directories
- Confirm runtime path configuration
- Re-run health checks before resuming

## Failed Workflow Transition

- Investigate the current state and requested transition
- Do not force a bypass
- Refuse or archive the RFQ if the workflow cannot safely continue

## Missing Quote Pack

- Treat as a blocking artifact issue
- Do not proceed to review or proof capture

## Failed Review

- Record the refusal or blocker clearly
- Keep the workflow append-only

## Failed Proof Capture

- Stop the submission path
- Record the issue for operator follow-up
- Do not fabricate proof

## Duplicate Submission Risk

- Refuse additional submission attempts
- Preserve the original audit trail

## Safe Recovery Rule

- Recover by restoring the system, not by editing history
- Archive or refuse when the workflow cannot be safely repaired

