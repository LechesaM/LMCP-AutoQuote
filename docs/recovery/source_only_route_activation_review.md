# Source-Only Route Activation Review

Audit date: 2026-07-16
Evidence matrix: `docs/recovery/runtime_route_difference_matrix.json`

## Summary

After SBD ownership repair, current source exposes 126 method/path pairs that are absent from the running process. These are grouped below by route family. Family classification uses the highest-risk route in the family.

Counts:

- Source-only method/path pairs: 126
- Risky source-only method/path pairs: 114
- Failed source router imports: 0
- Duplicate source routes: 0

## Family Review

| Family | Classification | Methods/paths | Activation recommendation |
| --- | --- | --- | --- |
| `/clean-ink-v3` | HIGH_RISK_OPERATIONAL | `GET /clean-ink-v3/status`; `POST /clean-ink-v3/extract`; `POST /clean-ink-v3/extract-latest` | Requires operator approval; extraction writes artifacts. |
| `/v31-smart-harvester` | HIGH_RISK_OPERATIONAL | `GET /v31-smart-harvester/status`; `GET /v31-smart-harvester/review-queue/status`; `POST /v31-smart-harvester/apply`; `POST /v31-smart-harvester/classify`; `POST /v31-smart-harvester/document-intelligence-dry-run`; `POST /v31-smart-harvester/extract-real-opportunities`; `POST /v31-smart-harvester/multi-portal-discovery`; `POST /v31-smart-harvester/review-queue-dry-run`; `POST /v31-smart-harvester/run-once`; `POST /v31-smart-harvester/run-radar-cycle` | Disable or gate before restart unless acquisition activation is explicitly approved. |
| `/v32-real-rfq-harvester` | HIGH_RISK_OPERATIONAL | `GET /v32-real-rfq-harvester/status`; `POST /v32-real-rfq-harvester/classify`; `POST /v32-real-rfq-harvester/filter`; `POST /v32-real-rfq-harvester/run-once` | Disable or gate before restart unless acquisition activation is explicitly approved. |
| `/v33-real-portal-rfq` | HIGH_RISK_OPERATIONAL | `GET /v33-real-portal-rfq/status`; `POST /v33-real-portal-rfq/extract-portal`; `POST /v33-real-portal-rfq/run-once` | Gate before restart; portal extraction can hit external sources. |
| `/v34-structured-rfq` | HIGH_RISK_OPERATIONAL | `GET /v34-structured-rfq/status`; `POST /v34-structured-rfq/extract-portal`; `POST /v34-structured-rfq/run-once` | Gate before restart; portal extraction can hit external sources. |
| `/v35-playwright-rfq` | HIGH_RISK_OPERATIONAL | `GET /v35-playwright-rfq/status`; `POST /v35-playwright-rfq/extract-portal`; `POST /v35-playwright-rfq/run-once` | Gate before restart; browser extraction must be operator approved. |
| `/v36-interactive-rfq` | HIGH_RISK_OPERATIONAL | `GET /v36-interactive-rfq/status`; `POST /v36-interactive-rfq/extract-portal`; `POST /v36-interactive-rfq/run-once` | Gate before restart; browser extraction must be operator approved. |
| `/v37-deep-rfq` | HIGH_RISK_OPERATIONAL | `GET /v37-deep-rfq/status`; `POST /v37-deep-rfq/enrich-many`; `POST /v37-deep-rfq/enrich-one`; `POST /v37-deep-rfq/run-from-v36` | Gate before restart; enrichment/download behavior must be reviewed. |
| `/v38-click-deep-rfq` | HIGH_RISK_OPERATIONAL | `GET /v38-click-deep-rfq/status`; `POST /v38-click-deep-rfq/enrich-one`; `POST /v38-click-deep-rfq/run-from-v36` | Gate before restart; browser/click behavior must be reviewed. |
| `/v39-true-navigation` | HIGH_RISK_OPERATIONAL | `GET /v39-true-navigation/status`; `POST /v39-true-navigation/enrich-one`; `POST /v39-true-navigation/run-from-v36` | Gate before restart; browser/navigation behavior must be reviewed. |
| `/v40-clickable-navigation` | HIGH_RISK_OPERATIONAL | `GET /v40-clickable-navigation/status`; `POST /v40-clickable-navigation/extract` | Gate before restart. |
| `/v43-auto-pricing` | SAFE_CONTROLLED_MUTATION | `GET /v43-auto-pricing/status`; `POST /v43-auto-pricing/auto-price-pdf`; `POST /v43-auto-pricing/auto-price-v42-json` | Requires operator approval; local pricing artifact generation only. |
| `/v44-quote-pack` | SAFE_CONTROLLED_MUTATION | `GET /v44-quote-pack/status`; `POST /v44-quote-pack/generate-from-pdf`; `POST /v44-quote-pack/generate-from-v43-json` | Requires operator approval; local quote-pack generation only. |
| `/v45-submission-pack` | SAFE_CONTROLLED_MUTATION | `GET /v45-submission-pack/status`; `POST /v45-submission-pack/prepare-from-pdf`; `POST /v45-submission-pack/prepare-from-v44-json`; `POST /v45-submission-pack/prepare-from-v44-workspace` | Requires operator approval; pack generation is not buyer submission. |
| `/v46-auto-submission` | AUTONOMOUS_OR_SUBMISSION | `GET /v46-auto-submission/status`; `POST /v46-auto-submission/submit-from-email-draft-json`; `POST /v46-auto-submission/submit-from-pdf`; `POST /v46-auto-submission/submit-from-v45-workspace` | Disable before restart unless manually reviewed and guarded. |
| `/v47-assisted-browser` | HIGH_RISK_OPERATIONAL | `GET /v47-assisted-browser/status`; `POST /v47-assisted-browser/run-from-plan` | Requires operator approval; browser route. |
| `/v47-deep-verification` | HIGH_RISK_OPERATIONAL | `GET /v47-deep-verification/status`; `POST /v47-deep-verification/run-audit` | Requires operator approval. |
| `/v47-final-submit` | AUTONOMOUS_OR_SUBMISSION | `GET /v47-final-submit/status`; `POST /v47-final-submit/guarded-submit` | Disable before restart unless final-submit guard is audited. |
| `/v47-live-browser` | HIGH_RISK_OPERATIONAL | `GET /v47-live-browser/status`; `POST /v47-live-browser/attach-and-assist` | Requires operator approval; browser route. |
| `/v47-portal-autofill` | HIGH_RISK_OPERATIONAL | `GET /v47-portal-autofill/status`; `POST /v47-portal-autofill/generate-plan` | Requires operator approval. |
| `/v47-portal-submission` | AUTONOMOUS_OR_SUBMISSION | `GET /v47-portal-submission/status`; `POST /v47-portal-submission/prepare-from-pdf`; `POST /v47-portal-submission/prepare-from-v45-workspace`; `POST /v47-portal-submission/record-proof` | Disable or gate; portal submission/proof behavior requires review. |
| `/v47-smart-upload` | AUTONOMOUS_OR_SUBMISSION | `GET /v47-smart-upload/status`; `POST /v47-smart-upload/attach-and-upload` | Disable before restart unless upload guard is audited. |
| `/v48-autonomous` | AUTONOMOUS_OR_SUBMISSION | `GET /v48-autonomous/history`; `GET /v48-autonomous/last-result`; `GET /v48-autonomous/status`; `POST /v48-autonomous/policy`; `POST /v48-autonomous/run-from-pdf`; `POST /v48-autonomous/run-from-v45-workspace` | Disable before restart unless autonomous guard is audited. |
| `/v49-1-detail-page-follow` | HIGH_RISK_OPERATIONAL | `GET /v49-1-detail-page-follow/status`; `POST /v49-1-detail-page-follow/follow` | Gate before restart. |
| `/v49-real-rfq-detail-navigation` | HIGH_RISK_OPERATIONAL | `GET /v49-real-rfq-detail-navigation/status`; `POST /v49-real-rfq-detail-navigation/analyse` | Gate before restart. |
| `/v50-7-etenders-navigation` through `/v50-9-10-tender-download-correlation` | HIGH_RISK_OPERATIONAL | 45 method/path pairs covering eTenders navigation, AJAX, document URL reconstruction, JSON parsing, status enumeration, local filtering, document download, browser interception, modal autoclick, hidden API discovery, document mapping, replay reconstruction, runtime interception, and correlation. | Keep disabled/gated until eTenders acquisition activation is explicitly approved. |

## Restart Implication

The source-only set is not safe to expose silently. Even though autonomous defaults are now disabled, multiple source-only route families can harvest, browse, download, upload, generate submission artifacts, or trigger final-submit-adjacent workflows. A controlled restart needs either explicit operator acceptance of these activations or a route feature-gate mechanism.
