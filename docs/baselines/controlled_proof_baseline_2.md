# Controlled Proof Baseline #2

Captured from a fresh clean-shell controlled proof run on 2026-06-04.
RFQ source: `CTRL-002` / `LMCP-CTRL-002`

| Field | Value |
| --- | --- |
| Runtime dir | `/private/tmp/lmcp_runtime_b2` |
| Controlled status | `controlled` |
| Workflow checks passed | `7` |
| Quote pack PDF | `/private/tmp/lmcp_runtime_b2/generated_quotes/CTRL-002__LMCP-CTRL-002/CTRL-002__LMCP-CTRL-002.pdf` |
| Pricing files | `/private/tmp/lmcp_runtime_b2/quote_compilation/CTRL-002__LMCP-CTRL-002/pricing_schedule_completed.json`, `/private/tmp/lmcp_runtime_b2/quote_compilation/CTRL-002__LMCP-CTRL-002/pricing_schedule_completed.csv` |
| Submission manifest | `/private/tmp/lmcp_runtime_b2/generated_quotes/CTRL_002_submission_pack_manifest.txt` |
| Submission pack ready count | `2` |
| Portal upload | `blocked` |
| Email send | `blocked` |
| Final submit | `blocked` |
| Proof log | `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_proof.json` |
| Endpoint log | `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_endpoints.json` |
| Report log | `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_report.json` |

Comparison to Baseline #1

- Same controlled status: `controlled`
- Same workflow stability: `7 / 7` checks passed
- Same safety posture: portal upload blocked, email send blocked, final submit blocked
- Same artifact classes: quote pack, pricing schedule, submission pack
- Different RFQ source: `CTRL-002` instead of `CTRL-001`
- Different quote identifiers and output paths, as expected
- Different pricing totals, as expected for the alternate RFQ:
  - Baseline #1 total quoted price: `160000.0`
  - Baseline #2 total quoted price: `200000.0`
  - Baseline #1 grand total inc VAT: `183999.95`
  - Baseline #2 grand total inc VAT: `229999.94`
- Submission pack ready count remained stable at `2`

Raw summary:

```text
log_path: /private/tmp/lmcp_runtime_b2/logs/controlled_runtime_proof.json
endpoint_log_path: /private/tmp/lmcp_runtime_b2/logs/controlled_runtime_endpoints.json
runtime_dir: /private/tmp/lmcp_runtime_b2
controlled_status: controlled
workflow_checks_passed: 7
quote_pack_pdf: /private/tmp/lmcp_runtime_b2/generated_quotes/CTRL-002__LMCP-CTRL-002/CTRL-002__LMCP-CTRL-002.pdf
pricing_files: /private/tmp/lmcp_runtime_b2/quote_compilation/CTRL-002__LMCP-CTRL-002/pricing_schedule_completed.json, /private/tmp/lmcp_runtime_b2/quote_compilation/CTRL-002__LMCP-CTRL-002/pricing_schedule_completed.csv
submission_manifest: /private/tmp/lmcp_runtime_b2/generated_quotes/CTRL_002_submission_pack_manifest.txt
submission_pack_ready_count: 2
safety: no_portal_upload=true, no_email_send=true, no_final_submit=true
```

Related logs:
- `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_proof.json`
- `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_endpoints.json`
- `/private/tmp/lmcp_runtime_b2/logs/controlled_runtime_report.json`
