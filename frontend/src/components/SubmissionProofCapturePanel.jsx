import { AlertTriangle, Clock3, FileDown, Save } from "lucide-react";

function safeText(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return fallback;
}

function asArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    return value
      .split(/\n|;|\|/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [value];
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function SubmissionProofCapturePanel({
  packId,
  authState,
  submissionProofState,
  submissionProofForm,
  onSubmissionProofChange,
  onSubmissionProofSave,
  onSubmissionProofRequest,
  onSubmissionProofDownload,
}) {
  const session = authState?.session || null;
  const proofSaveBlockedReason = session?.authenticated ? "" : "Login required. Operator session is missing or expired.";
  const proofLoadBlockedReason = session?.authenticated ? "" : "Login required. Operator session is missing or expired.";
  const proofExportBlockedReason = session?.authenticated ? "" : "Login required. Operator session is missing or expired.";
  const submissionProof = submissionProofState?.data?.validation?.allowed === true
    ? (submissionProofState?.data?.submission_proof || null)
    : null;
  const submissionProofStatus = safeText(submissionProofState?.data?.validation?.status || submissionProofState?.data?.status, "missing");
  const submissionProofSavedStatus = submissionProofState?.data?.status === "ok" || submissionProofState?.data?.status === "invalid" ? "Saved" : "Missing";
  const submissionProofLastUpdated = safeText(submissionProof?.saved_at || submissionProofState?.data?.saved_at || submissionProofState?.data?.validation?.submission_proof?.saved_at, "Not loaded");

  return (
    <div className="submission-gate-proof-card">
      <div className="submission-gate-proof-head">
        <div>
          <h3>Submission Proof Capture</h3>
          <p>Save a local proof record after the portal submission is completed outside this system.</p>
        </div>
        <div className="submission-gate-proof-actions">
          <button type="button" onClick={onSubmissionProofSave} disabled={!packId || submissionProofState.loading || Boolean(proofSaveBlockedReason)}>
            <Save size={15} />
            {submissionProofState.loading ? "Saving" : "Save Proof"}
          </button>
          <button type="button" onClick={onSubmissionProofRequest} disabled={!packId || submissionProofState.loading || Boolean(proofLoadBlockedReason)}>
            <Clock3 size={15} />
            {submissionProofState.loading ? "Loading" : "Load Proof"}
          </button>
          {packId ? (
            <button type="button" onClick={onSubmissionProofDownload} disabled={!submissionProof || Boolean(proofExportBlockedReason)}>
              <FileDown size={15} />
              Download Proof JSON
            </button>
          ) : null}
        </div>
      </div>
      {proofSaveBlockedReason ? <div className="submission-gate-warning"><AlertTriangle size={15} />{proofSaveBlockedReason}</div> : null}
      {proofLoadBlockedReason && proofLoadBlockedReason !== proofSaveBlockedReason ? <div className="submission-gate-warning"><AlertTriangle size={15} />{proofLoadBlockedReason}</div> : null}
      {proofExportBlockedReason && proofExportBlockedReason !== proofLoadBlockedReason ? <div className="submission-gate-warning"><AlertTriangle size={15} />{proofExportBlockedReason}</div> : null}
      {submissionProofState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{submissionProofState.error}</div> : null}
      {submissionProofState.data?.validation?.status === "invalid" ? (
        <div className="submission-gate-warning"><AlertTriangle size={15} />{safeText(submissionProofState.data?.validation?.blocked_reason, "Submission proof record is invalid.")}</div>
      ) : null}
      <div className="submission-gate-proof-form">
        <label>
          <span>Submitted By</span>
          <input value={submissionProofForm.submitted_by} onChange={(event) => onSubmissionProofChange("submitted_by", event.target.value)} placeholder="Operator name" />
        </label>
        <label>
          <span>Submission Timestamp</span>
          <input value={submissionProofForm.submission_timestamp} onChange={(event) => onSubmissionProofChange("submission_timestamp", event.target.value)} placeholder="2026-05-15T09:30:00+02:00" />
        </label>
        <label>
          <span>Portal Name</span>
          <input value={submissionProofForm.portal_name} onChange={(event) => onSubmissionProofChange("portal_name", event.target.value)} placeholder="Buyer portal" />
        </label>
        <label>
          <span>Portal Reference</span>
          <input value={submissionProofForm.portal_reference} onChange={(event) => onSubmissionProofChange("portal_reference", event.target.value)} placeholder="Confirmation / receipt / reference number" />
        </label>
        <label className="wide">
          <span>Proof Notes</span>
          <textarea value={submissionProofForm.proof_notes} onChange={(event) => onSubmissionProofChange("proof_notes", event.target.value)} placeholder="Short note about the external submission proof." rows={4} />
        </label>
        <label>
          <span>Buyer Reference</span>
          <input value={submissionProofForm.buyer_reference} onChange={(event) => onSubmissionProofChange("buyer_reference", event.target.value)} placeholder="Optional buyer reference" />
        </label>
        <label>
          <span>Confirmation Message</span>
          <input value={submissionProofForm.confirmation_message} onChange={(event) => onSubmissionProofChange("confirmation_message", event.target.value)} placeholder="Optional confirmation text" />
        </label>
        <label className="wide">
          <span>Screenshot Notes</span>
          <textarea value={submissionProofForm.screenshot_notes} onChange={(event) => onSubmissionProofChange("screenshot_notes", event.target.value)} placeholder="Optional notes about attached screenshots" rows={3} />
        </label>
        <label className="wide">
          <span>Uploaded Files</span>
          <textarea value={submissionProofForm.uploaded_files} onChange={(event) => onSubmissionProofChange("uploaded_files", event.target.value)} placeholder="One file name per line" rows={3} />
        </label>
        <label className="wide">
          <span>Screenshot Paths</span>
          <textarea value={submissionProofForm.screenshot_paths} onChange={(event) => onSubmissionProofChange("screenshot_paths", event.target.value)} placeholder="One screenshot file path per line" rows={3} />
        </label>
        <label>
          <span>Email Proof</span>
          <input value={submissionProofForm.email_proof} onChange={(event) => onSubmissionProofChange("email_proof", event.target.value)} placeholder="Email subject or message reference" />
        </label>
        <label>
          <span>Portal Proof</span>
          <input value={submissionProofForm.portal_proof} onChange={(event) => onSubmissionProofChange("portal_proof", event.target.value)} placeholder="Portal confirmation text or identifier" />
        </label>
        <label>
          <span>Receipt Reference</span>
          <input value={submissionProofForm.receipt_reference} onChange={(event) => onSubmissionProofChange("receipt_reference", event.target.value)} placeholder="Receipt / confirmation number" />
        </label>
        <label>
          <span>Proof Reference</span>
          <input value={submissionProofForm.proof_reference} onChange={(event) => onSubmissionProofChange("proof_reference", event.target.value)} placeholder="Internal proof reference" />
        </label>
      </div>
      {submissionProof ? (
        <>
          <div className="submission-gate-proof-summary">
            <div><span>Proof Saved</span><b>{submissionProofSavedStatus}</b></div>
            <div><span>Last Updated</span><b>{submissionProofLastUpdated}</b></div>
            <div><span>Status</span><b>{submissionProofStatus.replaceAll("_", " ")}</b></div>
            <div><span>Uploaded Files</span><b>{asArray(submissionProof.uploaded_files).length}</b></div>
          </div>
          <div className="submission-gate-proof-meta">
            <div><span>Submitted By</span><b>{safeText(submissionProof.submitted_by, "Unknown")}</b></div>
            <div><span>Portal</span><b>{safeText(submissionProof.portal_name, "Unknown")}</b></div>
            <div><span>Reference</span><b>{safeText(submissionProof.portal_reference, "No reference saved")}</b></div>
            <div><span>Submission Timestamp</span><b>{formatDateTime(submissionProof.submission_timestamp)}</b></div>
          </div>
          {submissionProof.proof_notes ? <pre className="submission-gate-proof-notes">{safeText(submissionProof.proof_notes)}</pre> : null}
        </>
      ) : (
        <div className="submission-gate-empty">No submission proof has been saved for this pack yet. Final submit remains locked.</div>
      )}
    </div>
  );
}
