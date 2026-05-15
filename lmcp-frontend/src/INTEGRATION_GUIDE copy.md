# Step 4 - Tender Drawer Action Wiring

Files:
- src/services/tenderDrawerActions.js
- src/components/TenderDetailDrawer.jsx

What this adds:
- Open RFQ Document button
- Open Quote Pack PDF button
- Open Submission Proof button
- Submit Now button wired to available backend submission endpoints
- Action feedback messages in the drawer

Assumptions:
- The backend may expose URLs in raw tender fields such as:
  document_url, rfq_document_url, source_url, quote_pack_url, submission_proof_url
- Submit Now tries:
  /tender-pipeline/run
  /submission-scheduler/run-now
  /autonomous/run-once
