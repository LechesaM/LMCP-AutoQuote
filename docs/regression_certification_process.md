# Regression Certification Process

This process protects the proven controlled workflow from silent regressions.

## Purpose

Use this process whenever a change might affect:

- controlled status reporting
- workflow checks
- quote generation
- pricing schedule generation
- submission package generation
- safety controls

## Reference Baselines

- Baseline #1: [controlled_proof_baseline.md](./baselines/controlled_proof_baseline.md)
- Baseline #2: [controlled_proof_baseline_2.md](./baselines/controlled_proof_baseline_2.md)
- Controlled Production Certification: [controlled_production_certification.md](./baselines/controlled_production_certification.md)

## Weekly Workflow

1. Run `make controlled-proof` from a clean shell.
2. Capture the report output and proof artifacts.
3. Compare the run against Baseline #1, Baseline #2, and the certification record.
4. Record any variance, even if the run still passes.
5. Approve the change only if the observed behavior is still within the certified envelope.

## Required Checks

Track these fields on every run:

- `workflow_checks_passed`
- `blocked_count`
- quote generation success
- submission package success
- safety control status

## Review Rule

- Approve if the run matches the certified controlled behavior and no new warnings or degraded checks appear.
- Reject if any safety control changes, any workflow check degrades, or the proof artifacts stop matching the expected controlled path.

