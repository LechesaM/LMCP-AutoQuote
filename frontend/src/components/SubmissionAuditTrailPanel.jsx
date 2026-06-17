import { AlertTriangle, Clock3, FileText } from "lucide-react";

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

function normalizeNumber(value, fallback = 0) {
  if (value === undefined || value === null || value === "") return fallback;
  const n = Number(String(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? n : fallback;
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function auditTrailEventSummary(event) {
  const payload = event && typeof event.payload === "object" && !Array.isArray(event.payload) ? event.payload : {};
  const parts = [];
  if (safeText(payload.reason_code)) parts.push(safeText(payload.reason_code, "").replaceAll("_", " "));
  if (Object.prototype.hasOwnProperty.call(payload, "allowed")) parts.push(payload.allowed ? "allowed" : "blocked");
  if (safeText(payload.blocked_reason)) parts.push(safeText(payload.blocked_reason, 180));
  if (safeText(payload.status)) parts.push(`status: ${safeText(payload.status, 40)}`);
  if (Object.prototype.hasOwnProperty.call(payload, "warning_count")) parts.push(`warnings: ${safeText(payload.warning_count)}`);
  if (Object.prototype.hasOwnProperty.call(payload, "count")) parts.push(`count: ${safeText(payload.count)}`);
  if (Object.prototype.hasOwnProperty.call(payload, "uploaded_file_count")) parts.push(`files: ${safeText(payload.uploaded_file_count)}`);
  return parts.length ? parts.join(" · ") : "Audit event recorded locally.";
}

export default function SubmissionAuditTrailPanel({ packId, auditTrailState, auditTrailJsonDownloadUrl, onAuditTrailRequest }) {
  const auditTrail = auditTrailState.data;
  const auditTrailEvents = asArray(auditTrail?.events);
  const auditTrailLatestEvents = auditTrailEvents.slice(-10).reverse();
  const auditTrailWarningCount = normalizeNumber(auditTrail?.warning_count, 0);

  return (
    <div className="submission-gate-audit-trail-card">
      <div className="submission-gate-audit-trail-head">
        <div>
          <h3>Audit Trail</h3>
          <p>Pack-local JSONL event history for submission-gate actions.</p>
        </div>
        <div className="submission-gate-audit-trail-actions">
          <button type="button" onClick={onAuditTrailRequest} disabled={!packId || auditTrailState.loading}>
            <Clock3 size={15} />
            {auditTrailState.loading ? "Loading" : "Load Audit Trail"}
          </button>
          {auditTrailJsonDownloadUrl ? (
            <a href={auditTrailJsonDownloadUrl} download>
              <FileText size={15} />
              Download Audit Trail JSON
            </a>
          ) : null}
        </div>
      </div>
      {auditTrailState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{auditTrailState.error}</div> : null}
      {auditTrail ? (
        <div className="submission-gate-audit-trail-summary">
          <div><span>Events</span><b>{auditTrailEvents.length}</b></div>
          <div><span>Warnings</span><b>{auditTrailWarningCount}</b></div>
          <div><span>Path</span><b>{safeText(auditTrail.audit_trail_path, "runtime/quote_compilation/.../audit_trail.jsonl")}</b></div>
        </div>
      ) : null}
      <div className="submission-gate-audit-trail-events">
        {(auditTrailLatestEvents.length ? auditTrailLatestEvents : [{ event_type: "audit_trail_pending", timestamp: "", payload: {}, status: "pending" }]).map((event, index) => (
          <div className={`submission-gate-audit-trail-event ${safeText(event.status || event.event_type, "neutral").toLowerCase()}`} key={`${event.event_id || event.event_type || "audit-trail"}-${index}`}>
            <time>{formatDateTime(event.timestamp)}</time>
            <b>{safeText(event.event_type, "event").replaceAll("_", " ")}</b>
            <span>{safeText(event.event_id, "event")}</span>
            <p>{auditTrailEventSummary(event)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
