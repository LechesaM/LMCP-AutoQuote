import { AlertTriangle, FileArchive, FileDown, FileText } from "lucide-react";

function safeText(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return fallback;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

export default function SubmissionEvidenceBundlePanel({
  packId,
  evidenceBundleState,
  evidenceBundleJsonDownloadUrl,
  onEvidenceBundleRequest,
  evidenceBundle,
  submissionProof,
  submissionProofStatus,
}) {
  const evidenceBundleWarnings = asArray(evidenceBundle?.bundle_warnings);
  const evidenceBundleAuditTrail = asArray(evidenceBundle?.audit_trail);
  const evidenceBundleAuditCount = normalizeNumber(evidenceBundle?.audit_event_count, evidenceBundleAuditTrail.length);
  const evidenceBundleWarningCount = normalizeNumber(evidenceBundle?.audit_warning_count, 0);
  const evidenceBundleGeneratedAt = safeText(evidenceBundle?.generated_at, "Not loaded");
  const evidenceBundleManualPresent = Boolean(evidenceBundle?.manual_completion_record);
  const evidenceBundleFinalLocked = evidenceBundle?.final_submit_locked !== false;
  const evidenceBundleAutomatedDisabled = evidenceBundle?.automated_submit_disabled !== false;
  const evidenceBundleSnapshotStatus = safeText(evidenceBundle?.evidence_snapshot_verification_status, "unknown");
  const evidenceBundleSnapshotHash = safeText(evidenceBundle?.evidence_snapshot_hash, "Not loaded");

  return (
    <div className="submission-gate-bundle-card">
      <div className="submission-gate-bundle-head">
        <div>
          <h3>Evidence Bundle</h3>
          <p>Single JSON bundle combining the pack-local submission evidence records.</p>
        </div>
        <div className="submission-gate-bundle-actions">
          <span className="submission-gate-bundle-badge">
            <FileArchive size={13} />
            {evidenceBundleFinalLocked ? "Locked" : "Unlocked"}
          </span>
          <button type="button" onClick={onEvidenceBundleRequest} disabled={!packId || evidenceBundleState.loading}>
            <FileDown size={15} />
            {evidenceBundleState.loading ? "Loading" : "Load Bundle"}
          </button>
          {evidenceBundle ? (
            <a href={evidenceBundleJsonDownloadUrl} download>
              <FileText size={15} />
              Download Evidence Bundle JSON
            </a>
          ) : null}
        </div>
      </div>
      {evidenceBundleState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{evidenceBundleState.error}</div> : null}
      {evidenceBundle ? (
        <>
          <div className="submission-gate-bundle-summary">
            <div><span>Generated At</span><b>{evidenceBundleGeneratedAt}</b></div>
            <div><span>Manual Completion</span><b>{evidenceBundleManualPresent ? "Present" : "Missing"}</b></div>
            <div><span>Submission Proof</span><b>{submissionProof ? "Present" : "Missing"}</b></div>
            <div><span>Audit Events</span><b>{evidenceBundleAuditCount}</b></div>
            <div><span>Warning Count</span><b>{evidenceBundleWarningCount}</b></div>
            <div><span>Final Submit Locked</span><b>{evidenceBundleFinalLocked ? "Yes" : "No"}</b></div>
            <div><span>Automated Submit Disabled</span><b>{evidenceBundleAutomatedDisabled ? "Yes" : "No"}</b></div>
            <div><span>Snapshot Status</span><b>{safeText(evidenceBundleSnapshotStatus, "unknown").replaceAll("_", " ")}</b></div>
            <div><span>Snapshot Hash</span><b>{evidenceBundleSnapshotHash}</b></div>
            <div><span>Proof Status</span><b>{safeText(submissionProofStatus, "missing").replaceAll("_", " ")}</b></div>
          </div>
          <div className="submission-gate-bundle-columns">
            <div>
              <h4>Bundle Warnings</h4>
              <div className="submission-risk-list">
                {(evidenceBundleWarnings.length ? evidenceBundleWarnings : ["No bundle warnings reported."]).map((item, index) => (
                  <p className="submission-risk warning" key={`bundle-warning-${item}-${index}`}>{safeText(item)}</p>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="submission-gate-empty">Evidence bundle has not been loaded yet. Final submit remains locked.</div>
      )}
    </div>
  );
}
