export const REQUEST_TIMEOUT_MS = 8000;

export const SUBMISSION_ENDPOINTS = [
  "/rfq-lifecycle/status",
  "/rfq-lifecycle/recent",
  "/rfq-lifecycle/report",
  "/submission-history/recent",
  "/submission-proof/latest",
  "/submission-pack/status",
  "/portal-submission/status",
  "/portal-submission/classify",
  "/health",
];

export const DRY_RUN_ENDPOINTS = [
  "/rfq-lifecycle/upload-dry-run/latest",
  "/rfq-lifecycle/upload-dry-runs/latest",
  "/upload-dry-run/latest",
  "/upload-dry-run/status",
  "/upload-readiness/status",
];

export const BINDER_ENDPOINTS = [
  "/quote-compilation/submission-binders",
  "/quote-compilation/packs/latest",
  "/quote-compilation/packs",
];

export const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
export const DRAWER_TABS = ["Overview", "Upload Artifacts", "Buyer Forms", "BOQ / Pricing", "Proofs", "Portal", "Submission Binder", "Risks / Blockers"];
export const SAFETY_LOCKS = ["no_email_send", "no_portal_upload", "no_final_submit", "controlled_dry_run_only"];
export const BINDER_SAFETY_LABELS = ["LOCAL BINDER ONLY", "NOT SUBMITTED", "NOT EMAILED", "NOT UPLOADED", "FINAL SUBMIT LOCKED"];
export const OPERATOR_ROLE_LABELS = {
  preparer: "Preparer",
  reviewer: "Reviewer",
  submitter: "Submitter",
  admin: "Admin",
};
export const OPERATOR_ACTION_ALLOWED_ROLES = {
  proof_save: ["submitter", "admin"],
  proof_load: ["submitter", "admin"],
  proof_export: ["submitter", "admin"],
  archive_create: ["admin"],
  archive_export: ["admin"],
};

export const DEMO_SUBMISSIONS = [
  {
    id: "demo-submission-centre",
    rfq_reference: "RFQ-SUB-DEMO-001",
    title: "Controlled upload dry-run preview",
    buyer: "Demo Buyer",
    province: "GP",
    closing_date: new Date(Date.now() + 3 * 86400000).toISOString(),
    submission_status: "Dry-Run Review",
    dry_run_status: "Controlled Only",
    portal_status: "Compatible",
    proof_status: "Pending",
    upload_readiness_score: 72,
    quote_pack_readiness_score: 82,
    required_artifacts: ["Buyer form", "Pricing schedule", "BOQ", "Completed SBD forms", "Generated quote pack"],
    found_artifacts: ["Buyer form", "Pricing schedule", "BOQ", "Generated quote pack"],
    missing_artifacts: ["Completed SBD forms"],
    buyer_forms: [{ name: "Buyer RFQ form.pdf", type: "Buyer Form", status: "Ready" }],
    pricing_schedules: [{ name: "Pricing schedule.xlsx", type: "Pricing Schedule", status: "Ready" }],
    boqs: [{ name: "Bill of quantities.xlsx", type: "BOQ", status: "Ready" }],
    completed_sbd_forms: [],
    generated_quote_files: [{ name: "LMCP quote pack.pdf", type: "Quote Pack", status: "Ready" }],
    proofs: [],
    risks: ["Demo fallback data shown because live submission rows did not load"],
    blockers: ["Completed SBD forms missing"],
    recommended_next_step: "Hold for missing artifacts",
    _demo: true,
    _sources: ["frontend fallback"],
  },
];
