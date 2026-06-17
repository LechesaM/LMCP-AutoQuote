import { API_BASE } from "../services/api";
import { FileArchive, FileCheck2, FileSpreadsheet, FileText, LockKeyhole, PauseCircle, ShieldCheck, ShieldAlert } from "lucide-react";

const BINDER_SAFETY_LABELS = ["LOCAL BINDER ONLY", "NOT SUBMITTED", "NOT EMAILED", "NOT UPLOADED", "FINAL SUBMIT LOCKED"];
const OPERATOR_ROLE_LABELS = {
  preparer: "Preparer",
  reviewer: "Reviewer",
  submitter: "Submitter",
  admin: "Admin",
};
const OPERATOR_ACTION_ALLOWED_ROLES = {
  proof_save: ["submitter", "admin"],
  proof_load: ["submitter", "admin"],
  proof_export: ["submitter", "admin"],
  archive_create: ["admin"],
  archive_export: ["admin"],
};

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

function formatDate(value) {
  if (!value) return "No closing date";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No closing date");
  return date.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "2-digit" });
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function normalizeSessionRole(role) {
  const normalizedRole = safeText(role).toLowerCase();
  return OPERATOR_ROLE_LABELS[normalizedRole] ? normalizedRole : "";
}

function operatorRoleLabel(role) {
  const normalizedRole = normalizeSessionRole(role);
  return OPERATOR_ROLE_LABELS[normalizedRole] || "Unknown";
}

function operatorCan(role, action) {
  const normalizedRole = normalizeSessionRole(role);
  return (OPERATOR_ACTION_ALLOWED_ROLES[action] || []).includes(normalizedRole);
}

function operatorBlockedReason(session, action) {
  if (!session?.authenticated) return "Login required. Operator session is missing or expired.";
  const role = normalizeSessionRole(session?.operator?.role);
  if (!role) return "Authenticated operator role is not recognized.";
  if (operatorCan(role, action)) return "";
  if (action.startsWith("proof_")) return `${operatorRoleLabel(role)} role cannot access manual submission proof actions.`;
  if (action.startsWith("archive_")) return `${operatorRoleLabel(role)} role cannot manage compliance archives.`;
  return `${operatorRoleLabel(role)} role cannot use this action.`;
}

function statusTone(status) {
  const lower = safeText(status).toLowerCase();
  if (lower.includes("ready") || lower.includes("compatible") || lower.includes("submitted") || lower.includes("verified") || lower.includes("available") || lower.includes("allowed") || lower.includes("complete") || lower.includes("ok")) return "green";
  if (lower.includes("review") || lower.includes("pending") || lower.includes("dry") || lower.includes("hold") || lower.includes("warning") || lower.includes("unknown") || lower.includes("locked")) return "amber";
  if (lower.includes("blocked") || lower.includes("missing") || lower.includes("fail") || lower.includes("reject")) return "red";
  return "neutral";
}

function scoreTone(score) {
  const value = Number(score || 0);
  if (value >= 85) return "green";
  if (value >= 60) return "amber";
  return "red";
}

function ScoreChip({ label, score }) {
  return (
    <span className={`submission-score-chip ${scoreTone(score)}`}>
      <small>{label}</small>
      <b>{score ?? 0}</b>
    </span>
  );
}

function ArtifactList({ items, empty }) {
  if (!items.length) return <div className="submission-empty-inline">{empty}</div>;
  return (
    <div className="submission-artifact-list">
      {items.map((item, index) => (
        <div className="submission-artifact" key={`${item.type}-${item.name}-${index}`}>
          {item.type === "BOQ" || item.type === "Pricing Schedule" ? <FileSpreadsheet size={16} /> : item.type === "Proof" ? <FileCheck2 size={16} /> : item.type === "Generated Quote File" ? <FileArchive size={16} /> : <FileText size={16} />}
          <div>
            <b>{item.name}</b>
            <span>{item.type}{item.status ? ` · ${item.status}` : ""}</span>
          </div>
          {item.url ? <a href={item.url.startsWith("http") ? item.url : `${API_BASE}${item.url}`} target="_blank" rel="noreferrer">Open</a> : null}
        </div>
      ))}
    </div>
  );
}

function BinderSafetyLabels() {
  return (
    <div className="submission-binder-labels">
      {BINDER_SAFETY_LABELS.map((label) => (
        <span key={label}>
          <LockKeyhole size={13} />
          {label}
        </span>
      ))}
    </div>
  );
}

function BinderReadinessFlags({ binder }) {
  return (
    <div className="submission-binder-flags">
      <div className={binder.pricing_completed ? "complete" : "review"}><span>Pricing</span><b>{binder.pricing_completed ? "Complete" : "Review"}</b></div>
      <div className={binder.formal_quote_generated ? "complete" : "review"}><span>Formal Quote</span><b>{binder.formal_quote_generated ? "Generated" : "Missing"}</b></div>
      <div className={binder.returnables_review_completed ? "complete" : "review"}><span>Returnables</span><b>{binder.returnables_review_completed ? "Reviewed" : "Review"}</b></div>
    </div>
  );
}

function BinderOperatorControls({ binder, operatorState, onOperatorAction }) {
  if (!binder) return null;
  const stateKey = `binder:${binder.pack_id}`;
  const localDecision = operatorState[stateKey];
  return (
    <>
      <div className="submission-binder-actions">
        <button type="button" onClick={() => onOperatorAction(stateKey, "Binder Accepted for Review")}><ShieldCheck size={15} />Binder Accepted for Review</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Needs Binder Fix")}><ShieldAlert size={15} />Needs Binder Fix</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Needs Returnables Fix")}><FileCheck2 size={15} />Needs Returnables Fix</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Hold Submission Candidate")}><PauseCircle size={15} />Hold Submission Candidate</button>
      </div>
      {localDecision ? <div className="submission-local-state">Local binder state: {localDecision}</div> : null}
    </>
  );
}

function SubmissionBinderDetail({ binder, operatorState, onOperatorAction }) {
  if (!binder) {
    return (
      <div className="submission-binder-empty">
        <BinderSafetyLabels />
        <p>No local submission binder is linked to this RFQ yet.</p>
      </div>
    );
  }

  return (
    <div className="submission-binder-detail">
      <BinderSafetyLabels />
      <div className="submission-binder-headline">
        <div>
          <span className="submission-kicker">{binder.pack_id}</span>
          <h3>{binder.rfq_reference}</h3>
          <p>{binder.title} · {binder.buyer}</p>
        </div>
        <ScoreChip label="Binder" score={binder.submission_binder_score} />
      </div>
      <BinderReadinessFlags binder={binder} />
      <BinderOperatorControls binder={binder} operatorState={operatorState} onOperatorAction={onOperatorAction} />

      <h3 className="submission-section-title">Missing Items</h3>
      <div className="submission-risk-list">
        {(binder.missing_items.length ? binder.missing_items : ["No binder missing items detected."]).map((item, index) => <p className="submission-risk blocker" key={`binder-missing-${item}-${index}`}>{item}</p>)}
      </div>

      <h3 className="submission-section-title">Blockers</h3>
      <div className="submission-risk-list">
        {(binder.blockers.length ? binder.blockers : ["No binder blockers detected."]).map((item, index) => <p className="submission-risk blocker" key={`binder-blocker-${item}-${index}`}>{item}</p>)}
      </div>

      <h3 className="submission-section-title">Binder Files</h3>
      <ArtifactList items={binder.binder_files} empty="No generated binder files detected." />
      <h3 className="submission-section-title">Source Files</h3>
      <ArtifactList items={binder.source_files} empty="No binder source files detected." />
    </div>
  );
}

export default function SubmissionBinderReadinessPanel({ binders, focusedBinder, operatorState, onOperatorAction }) {
  const binder = focusedBinder || binders[0];
  const readyCount = binders.filter((item) => item.submission_binder_score >= 85 && !item.blockers.length).length;
  const blockerCount = binders.filter((item) => item.blockers.length > 0).length;

  return (
    <div className="submission-binder-section card">
      <div className="submission-binder-section-head">
        <div>
          <p className="eyebrow">Submission Binder Readiness</p>
          <h2>Local Binder Review</h2>
          <p className="muted">Read-only integration from local quote compilation packs. No upload, email, or final submit action is exposed.</p>
        </div>
        <BinderSafetyLabels />
      </div>

      {!binders.length ? (
        <div className="submission-binder-empty">
          <p>No local submission binders were found under runtime/quote_compilation.</p>
        </div>
      ) : (
        <>
          <div className="submission-binder-summary">
            <div><span>Binders</span><b>{binders.length}</b></div>
            <div><span>Ready &gt;=85</span><b>{readyCount}</b></div>
            <div><span>With Blockers</span><b>{blockerCount}</b></div>
            <div><span>Focused Score</span><b>{binder?.submission_binder_score ?? 0}</b></div>
          </div>

          {binder ? (
            <div className="submission-binder-focus">
              <div className="submission-binder-headline">
                <div>
                  <span className="submission-kicker">{binder.rfq_reference}</span>
                  <h3>{binder.title}</h3>
                  <p>{binder.buyer} · {formatDate(binder.created_at)}</p>
                </div>
                <ScoreChip label="Binder" score={binder.submission_binder_score} />
              </div>
              <BinderReadinessFlags binder={binder} />
              <BinderOperatorControls binder={binder} operatorState={operatorState} onOperatorAction={onOperatorAction} />
              <div className="submission-binder-columns">
                <div>
                  <h3 className="submission-section-title">Missing Items</h3>
                  <div className="submission-risk-list">
                    {(binder.missing_items.length ? binder.missing_items : ["No binder missing items detected."]).map((item, index) => <p className="submission-risk blocker" key={`focus-missing-${item}-${index}`}>{item}</p>)}
                  </div>
                </div>
                <div>
                  <h3 className="submission-section-title">Binder Files</h3>
                  <ArtifactList items={binder.binder_files} empty="No generated binder files detected." />
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
