# Controlled Production Certification

Status: `ready for operator-assisted use`
Date: `2026-06-04`

This document records the controlled-production evidence gathered from two fresh proof runs.

## Evidence

- Baseline #1: [controlled_proof_baseline.md](/Users/Shared/LMCP-AutoQuote-Server/docs/baselines/controlled_proof_baseline.md)
- Baseline #2: [controlled_proof_baseline_2.md](/Users/Shared/LMCP-AutoQuote-Server/docs/baselines/controlled_proof_baseline_2.md)
- Controlled proof runner: [scripts/run_controlled_shared_runtime_proof.sh](/Users/Shared/LMCP-AutoQuote-Server/scripts/run_controlled_shared_runtime_proof.sh)
- Proof report helper: [scripts/show_controlled_proof_report.py](/Users/Shared/LMCP-AutoQuote-Server/scripts/show_controlled_proof_report.py)
- Regression process: [docs/regression_certification_process.md](/Users/Shared/LMCP-AutoQuote-Server/docs/regression_certification_process.md)
- Weekly checklist: [docs/weekly_regression_certification_checklist.md](/Users/Shared/LMCP-AutoQuote-Server/docs/weekly_regression_certification_checklist.md)

## Certification Checklist

- [x] Baseline #1 passed
- [x] Baseline #2 passed
- [x] Different RFQ source passed
- [x] Fresh clean-shell run passed
- [x] Shared runtime passed
- [x] Safety controls passed
- [x] Final submit still blocked

## Observed Stability

- Controlled status remained `controlled` in both baselines.
- Workflow checks remained stable at `7 / 7`.
- Quote pack generation succeeded in both baselines.
- Pricing schedule generation succeeded in both baselines.
- Submission package generation succeeded in both baselines.
- Safety flags remained true in both baselines:
  - no portal upload
  - no email send
  - no autonomous final submit

## Notes

- Baseline #1 RFQ source: `CTRL-001` / `LMCP-CTRL-001`
- Baseline #2 RFQ source: `CTRL-002` / `LMCP-CTRL-002`
- The output paths and pricing totals differ between baselines, as expected for different RFQs.
- Final submission remains blocked by policy.

## Operator Guidance

Recommended maintenance mode from here:

- bug fixes only
- performance improvements only
- additional proof runs
- documentation and operator training

Avoid:

- major architectural changes
- re-enabling autonomous final submit
- enabling portal upload or email send in the controlled proof path
