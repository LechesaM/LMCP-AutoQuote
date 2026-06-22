# Trace Report: `FIN-SCM-TEN-0236`

## Scope

Single-RFQ trace from backend record to API contract to frontend/UI rendering.

This report answers one question:

Where does the mismatch begin for the document-status fields?

## RFQ Selected

- RFQ ID: `FIN-SCM-TEN-0236`
- Title: `Bid for the appointment of professional engineering services firm for the provision of upgrade of the existing NovaTec-P (Tc-99m) Generator Production Area and HVAC System.`
- Reason for selection:
  - stable stored live-queue record
  - buyer pack downloaded in backend state
  - quote-pack generated in backend state
  - no active reprocessing observed in the current evidence store

## Backend Record

Source:
- `runtime/live_rfqs.json`

Observed backend values:

| Field | Value |
| --- | --- |
| `buyer_pack_downloaded` | `true` |
| `boq_detected` | `true` |
| `pricing_schedule_detected` | `true` |
| `returnables_detected` | `true` |
| `quote_pack_generated` | `true` |
| `quote_ready` | `false` |
| `submission_status` | `pending` |
| `validation_status` | `needs_review` |
| `buyer_pack_status` | `downloaded` |
| `boq_status` | `detected` |
| `pricing_schedule_status` | `detected` |
| `returnables_status` | `detected` |
| `quote_pack_status` | `generated` |

Backend interpretation:
- the live store has the underlying acquisition/document signals present
- the record is still not `quote_ready`
- the blocker is not the absence of the document signals themselves

## API Response

Route:
- `GET /operations/rfqs/{tender_id}`

Contract layer:
- `app/api/operator_workflow_routes.py:27-30`
- `app/api/operator_workflow_routes.py:59-60`
- `app/api/operator_workflow_contracts.py:650-660`

Observed API values for the same RFQ:

| Field | Value |
| --- | --- |
| `buyer_pack_downloaded` | `false` |
| `boq_detected` | `false` |
| `pricing_schedule_detected` | `false` |
| `returnables_detected` | `false` |
| `quote_pack_generated` | `false` |

API interpretation:
- the detail contract does not preserve the backend document flags for this record
- the mismatch begins here, not in the frontend

## Frontend State

Frontend mapping:
- `frontend/src/components/RfqOperationsWorkspace.jsx:385-404`

Observed frontend state for the same field set:

| Field | Value |
| --- | --- |
| `buyer_pack_downloaded` | `false` |
| `boq_detected` | `false` |
| `pricing_schedule_detected` | `false` |
| `returnables_detected` | `false` |
| `quote_pack_generated` | `false` |

Frontend interpretation:
- the component derives its display state directly from the API record
- once the API drops the flags, the component state also drops them

## UI Rendering

Relevant rendering:
- `frontend/src/components/RfqOperationsWorkspace.jsx:1194-1199`

Visible UI result:

| UI Field | Displayed Value |
| --- | --- |
| Buyer Pack | `not_attempted` |
| BOQ | `not_attempted` |
| Pricing Schedule | `not_attempted` |
| Returnables | `not_attempted` |
| Quote Pack | `not_attempted` |

UI interpretation:
- the detail drawer reflects the API state, not the backend live record
- the document-status mismatch is visible to the user because the API contract strips the backend evidence

## Comparison Table

| Field | Backend | API | Frontend State | UI |
| --- | --- | --- | --- | --- |
| Buyer Pack | `true` | `false` | `false` | `not_attempted` |
| BOQ | `true` | `false` | `false` | `not_attempted` |
| Pricing Schedule | `true` | `false` | `false` | `not_attempted` |
| Returnables | `true` | `false` | `false` | `not_attempted` |
| Quote Pack | `true` | `false` | `false` | `not_attempted` |

## Where The Mismatch Begins

The first divergence occurs at the API contract layer:

- backend record contains the document flags
- API serialization returns them as false
- frontend state follows the API
- UI renders the frontend state

So the defect is not in the UI rendering itself.

Primary suspect:
- API serialization / contract mapping in `app/api/operator_workflow_contracts.py`

Secondary check:
- confirm the API contract is sourcing the same live record object that is stored in `runtime/live_rfqs.json`

## Conclusion

For `FIN-SCM-TEN-0236`, the backend evidence exists, but the API response does not preserve it. The first mismatch begins in the API contract layer, and the frontend/UI are faithfully rendering that incorrect contract response.
