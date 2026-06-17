import { AlertTriangle, FileCheck2, FileText, LockKeyhole, Save } from "lucide-react";
import { BINDER_SAFETY_LABELS } from "./submissionCentreConfig";

function safeText(value, fallback = "") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function SubmissionGateOverviewPanel({
  packId,
  gate,
  summaryState,
  summary,
  summaryDownloadUrl,
  onSummaryRequest,
  manualCompletionAllowed,
  finalSubmitBlockerMessage,
  manualCompletionState,
  manualCompletionForm,
  manualCompletion,
  manualDownloadUrl,
  onManualCompletionSave,
  onManualCompletionChange,
}) {
  const summarySteps = asArray(summary?.operator_next_steps);
  const summaryBlockers = asArray(summary?.blockers);
  const summaryMissingReturnables = asArray(summary?.missing_returnables);
  const gateBlockers = asArray(gate?.blockers);
  const gateMissingReturnables = asArray(gate?.missing_returnables);
  const safetyFlags = asArray(gate?.safety_flags);

  return (
    <>
      {!manualCompletionAllowed ? (
        <div className="submission-gate-warning">
          <AlertTriangle size={15} />
          {finalSubmitBlockerMessage}
        </div>
      ) : (
        <p className="submission-gate-message">Manual completion record saved. Final submission remains locked in this workspace.</p>
      )}
      <div className="submission-gate-pack-summary-card">
        <div className="submission-gate-pack-summary-head">
          <div>
            <h3>Submission Pack Summary</h3>
            <p>Read-only summary of local binder readiness for manual operator review.</p>
          </div>
          <div className="submission-gate-pack-summary-actions">
            <button type="button" onClick={onSummaryRequest} disabled={!packId || summaryState.loading}>
              <FileCheck2 size={15} />
              {summaryState.loading ? "Loading" : "Refresh Summary"}
            </button>
            {summaryDownloadUrl ? (
              <a href={summaryDownloadUrl} download>
                <FileText size={15} />
                Download Summary JSON
              </a>
            ) : null}
          </div>
        </div>
        {summaryState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{summaryState.error}</div> : null}
        {summary ? (
          <>
            <div className="submission-gate-pack-summary-grid">
              <div><span>Readiness</span><b>{safeText(summary.readiness_status, "Unknown")}</b></div>
              <div><span>Binder Score</span><b>{summary.binder_score ?? 0}</b></div>
              <div><span>Evidence Files</span><b>{summary.evidence_files_count ?? 0}</b></div>
              <div><span>Manual Completion</span><b>{summary.manual_completion_allowed ? "Saved" : "Required"}</b></div>
              <div><span>Final Submit</span><b>{summary.final_submit_locked ? "Locked" : "Blocked"}</b></div>
            </div>
            <div className="submission-gate-pack-summary-counts">
              <span>Checklist: {summary.checklist_available ? "available" : "unavailable"}</span>
              <span>Audit log: {summary.audit_log_available ? "available" : "unavailable"}</span>
              <span>Evidence manifest: {summary.evidence_manifest_available ? "available" : "unavailable"}</span>
            </div>
            <div className="submission-gate-pack-summary-columns">
              <div>
                <h4>Blockers</h4>
                <div className="submission-risk-list">
                  {(summaryBlockers.length ? summaryBlockers : ["No summary blockers reported."]).map((item, index) => (
                    <p className="submission-risk blocker" key={`summary-blocker-${item}-${index}`}>{safeText(item)}</p>
                  ))}
                </div>
              </div>
              <div>
                <h4>Missing Returnables</h4>
                <div className="submission-risk-list">
                  {(summaryMissingReturnables.length ? summaryMissingReturnables : ["No missing returnables reported by summary."]).map((item, index) => (
                    <p className="submission-risk blocker" key={`summary-returnable-${item}-${index}`}>{safeText(item)}</p>
                  ))}
                </div>
              </div>
            </div>
            <div className="submission-gate-pack-summary-steps">
              <h4>Next Manual Steps</h4>
              {(summarySteps.length ? summarySteps : ["Manual upload only. Final submission is blocked by design."]).map((step, index) => (
                <p key={`summary-step-${index}`}><b>{index + 1}</b>{safeText(step)}</p>
              ))}
            </div>
          </>
        ) : (
          <div className="submission-gate-empty">Submission pack summary has not loaded yet. Final submission remains locked.</div>
        )}
      </div>
      <div className="submission-gate-metrics">
        <div><span>Pack</span><b>{gate?.pack_id || packId}</b></div>
        <div><span>Binder Score</span><b>{gate?.binder_score ?? 0}</b></div>
        <div><span>Prepare</span><b>{gate?.can_prepare_submission ? "Allowed" : "Blocked"}</b></div>
        <div><span>Manual Completion</span><b>{manualCompletionAllowed ? "Saved" : "Required"}</b></div>
        <div><span>Final Submit</span><b>{gate?.can_submit_final ? "Allowed" : "Blocked"}</b></div>
      </div>
      <p className="submission-gate-message">{gate?.message || finalSubmitBlockerMessage}</p>
      <div className="submission-gate-columns">
        <div>
          <h3>Blockers</h3>
          <div className="submission-risk-list">
            {(gateBlockers.length ? gateBlockers : ["No binder gate blockers reported."]).map((item, index) => <p className="submission-risk blocker" key={`gate-blocker-${item}-${index}`}>{safeText(item)}</p>)}
          </div>
        </div>
        <div>
          <h3>Missing Returnables</h3>
          <div className="submission-risk-list">
            {(gateMissingReturnables.length ? gateMissingReturnables : ["No missing returnables reported by gate."]).map((item, index) => <p className="submission-risk blocker" key={`gate-returnable-${item}-${index}`}>{safeText(item)}</p>)}
          </div>
        </div>
      </div>
      <div className="submission-gate-safety">
        {safetyFlags.length ? safetyFlags.map(([key, value]) => (
          <span key={key}>
            <LockKeyhole size={13} />
            {key}: {String(value)}
          </span>
        )) : BINDER_SAFETY_LABELS.map((label) => (
          <span key={label}>
            <LockKeyhole size={13} />
            {label}
          </span>
        ))}
      </div>
      <div className="submission-gate-manual-card">
        <div className="submission-gate-manual-head">
          <div>
            <h3>Manual Completion Record</h3>
            <p>Save the reference only after you complete the portal action outside this system.</p>
          </div>
          <div className="submission-gate-manual-actions">
            <button type="button" onClick={onManualCompletionSave} disabled={!packId || manualCompletionState.loading}>
              <Save size={15} />
              {manualCompletionState.loading ? "Saving" : "Save Record"}
            </button>
            {manualDownloadUrl ? (
              <a href={manualDownloadUrl} download>
                <FileText size={15} />
                Download Completion JSON
              </a>
            ) : null}
          </div>
        </div>
        {manualCompletionState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{manualCompletionState.error}</div> : null}
        <div className="submission-gate-manual-form">
          <label>
            <span>Submitted By</span>
            <input
              value={manualCompletionForm.submitted_by}
              onChange={(event) => onManualCompletionChange("submitted_by", event.target.value)}
              placeholder="Operator name"
            />
          </label>
          <label>
            <span>Submitted At</span>
            <input
              value={manualCompletionForm.submitted_at}
              onChange={(event) => onManualCompletionChange("submitted_at", event.target.value)}
              placeholder="2026-05-15T09:30:00+02:00"
            />
          </label>
          <label>
            <span>Portal Name</span>
            <input
              value={manualCompletionForm.portal_name}
              onChange={(event) => onManualCompletionChange("portal_name", event.target.value)}
              placeholder="Buyer portal"
            />
          </label>
          <label>
            <span>Portal Reference</span>
            <input
              value={manualCompletionForm.portal_reference}
              onChange={(event) => onManualCompletionChange("portal_reference", event.target.value)}
              placeholder="Confirmation / receipt / reference number"
            />
          </label>
          <label className="wide">
            <span>Notes</span>
            <textarea
              value={manualCompletionForm.notes}
              onChange={(event) => onManualCompletionChange("notes", event.target.value)}
              placeholder="Short operator note about the external submission."
              rows={4}
            />
          </label>
          <label className="wide">
            <span>Uploaded File Names</span>
            <textarea
              value={manualCompletionForm.uploaded_file_names}
              onChange={(event) => onManualCompletionChange("uploaded_file_names", event.target.value)}
              placeholder="One file name per line"
              rows={4}
            />
          </label>
        </div>
        {manualCompletion ? (
          <>
            <div className="submission-gate-manual-summary">
              <div><span>Submitted By</span><b>{safeText(manualCompletion.submitted_by, "Unknown")}</b></div>
              <div><span>Submitted At</span><b>{formatDateTime(manualCompletion.submitted_at)}</b></div>
              <div><span>Portal</span><b>{safeText(manualCompletion.portal_name, "Unknown")}</b></div>
              <div><span>Files</span><b>{asArray(manualCompletion.uploaded_file_names).length}</b></div>
            </div>
            <div className="submission-gate-manual-meta">
              <div><span>Reference</span><b>{safeText(manualCompletion.portal_reference, "No reference saved")}</b></div>
              <div><span>Saved At</span><b>{formatDateTime(manualCompletion.saved_at)}</b></div>
            </div>
            {manualCompletion.notes ? <pre className="submission-gate-manual-notes">{safeText(manualCompletion.notes)}</pre> : null}
          </>
        ) : (
          <div className="submission-gate-empty">No manual completion record has been saved for this pack yet.</div>
        )}
      </div>
    </>
  );
}
