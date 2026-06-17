import { AlertTriangle, FileText, ShieldCheck } from "lucide-react";

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

function readinessFinalLabel(value) {
  const lower = safeText(value, "blocked").toLowerCase();
  if (lower.includes("ready")) return "Ready for manual submission";
  if (lower.includes("blocked")) return "Blocked";
  return safeText(value, "Blocked").replaceAll("_", " ");
}

export default function SubmissionReadinessChecklistPanel({
  packId,
  readinessChecklistState,
  readinessChecklistJsonDownloadUrl,
  onReadinessChecklistRequest,
  readinessChecklist,
}) {
  const readinessBlockers = asArray(readinessChecklist?.blockers);
  const readinessWarnings = asArray(readinessChecklist?.warnings);
  const manualSubmissionChecklist = asArray(readinessChecklist?.manual_submission_checklist);
  const readinessFinalStatus = safeText(readinessChecklist?.final_status, "blocked");
  const readinessManualStatus = safeText(readinessChecklist?.manual_completion_status, "missing");
  const readinessAuditCount = normalizeNumber(readinessChecklist?.audit_event_count, 0);
  const readinessAuditWarningCount = normalizeNumber(readinessChecklist?.audit_warning_count, 0);
  const readinessLatestAuditSummary = safeText(readinessChecklist?.latest_audit_event_summary, "No audit events recorded yet.");

  return (
    <div className="submission-gate-readiness-card">
      <div className="submission-gate-readiness-head">
        <div>
          <h3>Readiness Checklist</h3>
          <p>Pack-local readiness report for manual submission review and evidence capture.</p>
        </div>
        <div className="submission-gate-readiness-actions">
          <span className="submission-gate-readiness-badge">
            <ShieldCheck size={13} />
            {readinessFinalLabel(readinessFinalStatus)}
          </span>
          <button type="button" onClick={onReadinessChecklistRequest} disabled={!packId || readinessChecklistState.loading}>
            <FileText size={15} />
            {readinessChecklistState.loading ? "Loading" : "Load Checklist"}
          </button>
          {readinessChecklistJsonDownloadUrl ? (
            <a href={readinessChecklistJsonDownloadUrl} download>
              <FileText size={15} />
              Download Checklist JSON
            </a>
          ) : null}
        </div>
      </div>
      {readinessChecklistState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{readinessChecklistState.error}</div> : null}
      {readinessChecklist ? (
        <>
          <div className="submission-gate-readiness-summary">
            <div><span>Manual Completion Status</span><b>{readinessManualStatus.replaceAll("_", " ")}</b></div>
            <div><span>Manual Completion Present</span><b>{readinessChecklist.manual_completion_present ? "Yes" : "No"}</b></div>
            <div><span>Allowed</span><b>{readinessChecklist.manual_completion_allowed ? "Yes" : "No"}</b></div>
            <div><span>Can Submit Final</span><b>{readinessChecklist.can_submit_final ? "True" : "False"}</b></div>
            <div><span>Audit Events</span><b>{readinessAuditCount}</b></div>
          </div>
          <div className="submission-gate-readiness-meta">
            <div><span>Automated Submit</span><b>{readinessChecklist.automated_submit_disabled ? "Disabled" : "Enabled"}</b></div>
            <div><span>Audit Warnings</span><b>{readinessAuditWarningCount}</b></div>
            <div><span>Latest Audit Event</span><b>{readinessLatestAuditSummary}</b></div>
            <div><span>Pack ID</span><b>{safeText(readinessChecklist.pack_id || packId, "Unknown")}</b></div>
          </div>
          <div className="submission-gate-readiness-columns">
            <div>
              <h4>Blockers</h4>
              <div className="submission-risk-list">
                {(readinessBlockers.length ? readinessBlockers : ["No readiness blockers reported."]).map((item, index) => (
                  <p className="submission-risk blocker" key={`readiness-blocker-${item}-${index}`}>{safeText(item)}</p>
                ))}
              </div>
            </div>
            <div>
              <h4>Warnings</h4>
              <div className="submission-risk-list">
                {(readinessWarnings.length ? readinessWarnings : ["No readiness warnings reported."]).map((item, index) => (
                  <p className="submission-risk warning" key={`readiness-warning-${item}-${index}`}>{safeText(item)}</p>
                ))}
              </div>
            </div>
          </div>
          <div className="submission-gate-manual-checklist">
            <h4>Manual Submission Checklist</h4>
            <div className="submission-risk-list">
              {(manualSubmissionChecklist.length ? manualSubmissionChecklist : [
                { label: "Buyer pack reviewed", passed: false, reason: "Checklist not loaded yet." },
                { label: "Pricing reviewed", passed: false, reason: "Checklist not loaded yet." },
                { label: "Returnables reviewed", passed: false, reason: "Checklist not loaded yet." },
                { label: "Quote pack reviewed", passed: false, reason: "Checklist not loaded yet." },
                { label: "Submission method confirmed", passed: false, reason: "Checklist not loaded yet." },
                { label: "Final submit locked/manual-only", passed: true, reason: "Manual submission only." },
              ]).map((item, index) => (
                <p className={`submission-risk ${item.passed ? "ok" : "warning"}`} key={`${safeText(item.key || item.label, "manual-item")}-${index}`}>
                  {safeText(item.label, "Checklist item")}
                  {item.reason ? ` - ${safeText(item.reason)}` : ""}
                </p>
              ))}
            </div>
          </div>
        </>
      ) : (
        <div className="submission-gate-empty">Readiness checklist has not been loaded yet. Final submit remains locked.</div>
      )}
    </div>
  );
}
