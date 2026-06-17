import { AlertTriangle, Clock3, FileArchive, FileDown, FileText } from "lucide-react";
import { API_BASE } from "../services/api";
import {
  submissionEvidenceSnapshotExportPath,
  submissionPrintableReportHtmlPath,
  submissionPrintableReportPath,
} from "./submissionCentrePaths";

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

function statusTone(status) {
  const lower = safeText(status).toLowerCase();
  if (lower.includes("ready") || lower.includes("compatible") || lower.includes("submitted") || lower.includes("verified") || lower.includes("available") || lower.includes("allowed") || lower.includes("complete") || lower.includes("ok")) return "green";
  if (lower.includes("review") || lower.includes("pending") || lower.includes("dry") || lower.includes("hold") || lower.includes("warning") || lower.includes("unknown") || lower.includes("locked")) return "amber";
  if (lower.includes("blocked") || lower.includes("missing") || lower.includes("fail") || lower.includes("reject")) return "red";
  return "neutral";
}

export default function SubmissionEvidenceVerificationPanel({
  packId,
  submissionPrintableReportState,
  submissionEvidenceSnapshotState,
  onPrintableReportRequest,
  onEvidenceSnapshotRequest,
}) {
  const printableReportPreview = submissionPrintableReportState?.data || null;
  const evidenceSnapshot = submissionEvidenceSnapshotState?.data || null;
  const evidenceSnapshotReference = evidenceSnapshot?.rfq_reference || printableReportPreview?.rfq_reference || "";
  const printableReportReference = printableReportPreview?.rfq_reference || evidenceSnapshotReference;
  const printableReportUrl = packId && printableReportReference ? `${API_BASE}${submissionPrintableReportPath(packId, printableReportReference)}` : "";
  const printableReportHtmlUrl = packId && printableReportReference ? `${API_BASE}${submissionPrintableReportHtmlPath(packId, printableReportReference)}` : "";
  const printableReportStatus = safeText(printableReportPreview?.status, "unknown");
  const printableReportGeneratedAt = safeText(printableReportPreview?.generated_at, "Not loaded");
  const printableReportFinalLocked = printableReportPreview ? printableReportPreview.final_submit_locked !== false : true;
  const printableReportAutomatedDisabled = printableReportPreview ? printableReportPreview.automated_submit_disabled !== false : true;
  const printableReportAuditCount = Number.isFinite(Number(printableReportPreview?.audit_event_count)) ? Number(printableReportPreview?.audit_event_count) : 0;
  const printableReportWarningCount = Number.isFinite(Number(printableReportPreview?.audit_warning_count)) ? Number(printableReportPreview?.audit_warning_count) : 0;
  const printableReportSnapshotStatus = safeText(printableReportPreview?.evidence_snapshot_verification_status, "unknown");
  const printableReportSnapshotHash = safeText(printableReportPreview?.evidence_snapshot_hash, "Not loaded");
  const printableReportSnapshotGeneratedAt = safeText(printableReportPreview?.evidence_snapshot_generated_at, "Not loaded");
  const evidenceSnapshotStatus = safeText(evidenceSnapshot?.verification_status, "unknown");
  const evidenceSnapshotGeneratedAt = safeText(evidenceSnapshot?.generated_at, "Not loaded");
  const evidenceSnapshotHash = safeText(evidenceSnapshot?.evidence_bundle_hash, "Not loaded");
  const evidenceSnapshotReadinessHash = safeText(evidenceSnapshot?.readiness_checklist_hash, "Not loaded");
  const evidenceSnapshotAuditHash = safeText(evidenceSnapshot?.audit_trail_hash, "Not loaded");
  const evidenceSnapshotManualHash = safeText(evidenceSnapshot?.manual_completion_hash, "Not loaded");
  const evidenceSnapshotWarningCount = asArray(evidenceSnapshot?.warnings).length;
  const evidenceSnapshotJsonDownloadUrl = packId && evidenceSnapshotReference ? `${API_BASE}${submissionEvidenceSnapshotExportPath(packId, evidenceSnapshotReference)}` : "";

  return (
    <div className="submission-gate-verification-stack">
      <div className="submission-gate-printable-card">
        <div className="submission-gate-printable-head">
          <div>
            <h3>Printable Report</h3>
            <p>Browser-viewable compliance report built from the current pack evidence.</p>
          </div>
          <div className="submission-gate-printable-actions">
            <span className={`submission-gate-printable-badge ${statusTone(printableReportStatus)}`}>
              <FileText size={13} />
              {safeText(printableReportStatus, "unknown").replaceAll("_", " ")}
            </span>
            <button type="button" onClick={onPrintableReportRequest} disabled={!packId || submissionPrintableReportState.loading}>
              <Clock3 size={15} />
              {submissionPrintableReportState.loading ? "Loading" : "Load Report"}
            </button>
            <button type="button" onClick={() => window.open(printableReportUrl, "_blank", "noopener,noreferrer")} disabled={!packId}>
              <FileArchive size={15} />
              Open Printable Report
            </button>
            <button type="button" onClick={() => window.open(printableReportHtmlUrl, "_blank", "noopener,noreferrer")} disabled={!packId}>
              <FileDown size={15} />
              Open HTML Report
            </button>
          </div>
        </div>
        {submissionPrintableReportState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{submissionPrintableReportState.error}</div> : null}
        <div className="submission-gate-printable-summary">
          <div><span>Generated At</span><b>{printableReportGeneratedAt}</b></div>
          <div><span>Final Submit Locked</span><b>{printableReportFinalLocked ? "Yes" : "No"}</b></div>
          <div><span>Automated Submit Disabled</span><b>{printableReportAutomatedDisabled ? "Yes" : "No"}</b></div>
          <div><span>Audit Events</span><b>{printableReportAuditCount}</b></div>
          <div><span>Warning Count</span><b>{printableReportWarningCount}</b></div>
          <div><span>Proof Status</span><b>{safeText(printableReportPreview?.submission_proof_status, "unknown").replaceAll("_", " ")}</b></div>
          <div><span>Proof Hash</span><b>{safeText(printableReportPreview?.submission_proof_hash, "Not loaded")}</b></div>
          <div><span>Proof Saved</span><b>{safeText(printableReportPreview?.submission_proof_saved_at, "Not loaded")}</b></div>
          <div><span>Snapshot Status</span><b>{safeText(printableReportSnapshotStatus, "unknown").replaceAll("_", " ")}</b></div>
          <div><span>Snapshot Hash</span><b>{printableReportSnapshotHash}</b></div>
          <div><span>Snapshot Generated</span><b>{printableReportSnapshotGeneratedAt}</b></div>
        </div>
        <div className="submission-gate-printable-columns">
          <div>
            <h4>Preview Status</h4>
            <div className="submission-risk-list">
              <p className={`submission-risk ${printableReportPreview?.generated_at ? "ok" : "warning"}`}>{printableReportPreview ? "Printable report preview loaded locally." : "Load the report to preview its generated timestamp."}</p>
            </div>
          </div>
          <div>
            <h4>Print Notes</h4>
            <div className="submission-risk-list">
              <p className="submission-risk warning">Report content is read-only and safe for print-to-PDF.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="submission-gate-snapshot-card">
        <div className="submission-gate-snapshot-head">
          <div>
            <h3>Evidence Verification Snapshot</h3>
            <p>Pack-local hashes used to verify the evidence bundle, checklist, audit trail, and manual completion record.</p>
          </div>
          <div className="submission-gate-snapshot-actions">
            <span className={`submission-gate-snapshot-badge ${statusTone(evidenceSnapshotStatus)}`}>
              <FileArchive size={13} />
              {safeText(evidenceSnapshotStatus, "unknown").replaceAll("_", " ")}
            </span>
            <button type="button" onClick={onEvidenceSnapshotRequest} disabled={!packId || submissionEvidenceSnapshotState.loading}>
              <Clock3 size={15} />
              {submissionEvidenceSnapshotState.loading ? "Loading" : "Load Snapshot"}
            </button>
            {evidenceSnapshotJsonDownloadUrl ? (
              <a href={evidenceSnapshotJsonDownloadUrl} download>
                <FileText size={15} />
                Download Snapshot JSON
              </a>
            ) : null}
          </div>
        </div>
        {submissionEvidenceSnapshotState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{submissionEvidenceSnapshotState.error}</div> : null}
        <div className="submission-gate-snapshot-summary">
          <div><span>Generated At</span><b>{evidenceSnapshotGeneratedAt}</b></div>
          <div><span>Verification Status</span><b>{safeText(evidenceSnapshotStatus, "unknown").replaceAll("_", " ")}</b></div>
          <div><span>Warnings</span><b>{evidenceSnapshotWarningCount}</b></div>
          <div><span>Evidence Bundle Hash</span><b>{evidenceSnapshotHash}</b></div>
          <div><span>Readiness Checklist Hash</span><b>{evidenceSnapshotReadinessHash}</b></div>
          <div><span>Audit Trail Hash</span><b>{evidenceSnapshotAuditHash}</b></div>
          <div><span>Manual Completion Hash</span><b>{evidenceSnapshotManualHash}</b></div>
        </div>
        <div className="submission-gate-snapshot-columns">
          <div>
            <h4>Snapshot Warnings</h4>
            <div className="submission-risk-list">
              {(asArray(evidenceSnapshot?.warnings).length ? asArray(evidenceSnapshot?.warnings) : ["No snapshot warnings reported."]).map((item, index) => (
                <p className="submission-risk warning" key={`snapshot-warning-${item}-${index}`}>{safeText(item)}</p>
              ))}
            </div>
          </div>
          <div>
            <h4>Verification Notes</h4>
            <div className="submission-risk-list">
              <p className="submission-risk warning">Hashes are pack-local evidence markers only. Final submit remains locked.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
