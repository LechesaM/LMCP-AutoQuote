import { AlertTriangle, Archive, Clock3, FileDown, LockKeyhole, ShieldCheck } from "lucide-react";
import { OPERATOR_ACTION_ALLOWED_ROLES, OPERATOR_ROLE_LABELS } from "./submissionCentreConfig";

function safeText(value, fallback = "") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function statusTone(value) {
  const lower = safeText(value, "unknown").toLowerCase();
  if (lower.includes("ready") || lower.includes("ok") || lower.includes("complete") || lower.includes("allowed")) return "status-ready";
  if (lower.includes("warning") || lower.includes("review")) return "status-review";
  if (lower.includes("blocked") || lower.includes("missing") || lower.includes("error")) return "status-blocked";
  return "status-unknown";
}

function operatorRoleLabel(value) {
  const normalizedRole = normalizeSessionRole(value);
  return OPERATOR_ROLE_LABELS[normalizedRole] || "Unknown";
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

function normalizeSessionRole(role) {
  const normalizedRole = safeText(role).toLowerCase();
  return OPERATOR_ROLE_LABELS[normalizedRole] ? normalizedRole : "";
}

function operatorCan(role, action) {
  const normalizedRole = normalizeSessionRole(role);
  return (OPERATOR_ACTION_ALLOWED_ROLES[action] || []).includes(normalizedRole);
}

export default function SubmissionAccessArchivePanel({
  packId,
  authForm,
  authState,
  onAuthFormChange,
  onAuthLogin,
  onAuthBootstrap,
  onAuthLogout,
  submissionComplianceArchiveState,
  archiveCount: archiveCountProp,
  archiveWarningCount: archiveWarningCountProp,
  latestArchiveWarnings: latestArchiveWarningsProp,
  archiveBadgeStatus: archiveBadgeStatusProp,
  onComplianceArchiveCreateRequest,
  onComplianceArchivesRequest,
  onComplianceArchiveDownload,
}) {
  const session = authState?.session || null;
  const authLoading = Boolean(authState?.loading);
  const archives = asArray(submissionComplianceArchiveState?.data?.archives);
  const latestArchive = archives[0] || null;
  const archiveCount = normalizeNumber(archiveCountProp, normalizeNumber(submissionComplianceArchiveState?.data?.count, archives.length));
  const archiveWarningCount = normalizeNumber(archiveWarningCountProp, asArray(submissionComplianceArchiveState?.data?.warnings).length);
  const latestArchiveWarnings = asArray(latestArchiveWarningsProp).length ? asArray(latestArchiveWarningsProp) : (asArray(latestArchive?.warnings).length ? asArray(latestArchive?.warnings) : asArray(submissionComplianceArchiveState?.data?.warnings));
  const proofSaveBlockedReason = operatorBlockedReason(session, "proof_save");
  const archiveCreateBlockedReason = operatorBlockedReason(session, "archive_create");
  const archiveExportBlockedReason = operatorBlockedReason(session, "archive_export");
  const operatorStatusMessage = archiveCreateBlockedReason || proofSaveBlockedReason || "Authenticated operator has access to the enabled manual-only actions.";
  const archiveBadgeStatus = archiveBadgeStatusProp || latestArchive?.verification_status || (archives.length ? submissionComplianceArchiveState?.data?.status : "unknown") || "unknown";

  return (
    <>
      <div className="submission-gate-operator-panel">
        <div className="submission-gate-operator-head">
          <div>
            <h3>Operator Access</h3>
            <p>Local operator login and bootstrap controls for the controlled workspace.</p>
          </div>
          <div className={`submission-gate-operator-badge ${statusTone(session?.authenticated ? (safeText(session?.operator?.role, "").toLowerCase() === "admin" ? "ready" : "review") : "blocked")}`}>
            {session?.authenticated ? <ShieldCheck size={13} /> : <LockKeyhole size={13} />}
            {session?.authenticated ? "Authenticated" : "Locked"}
          </div>
        </div>
        <div className="submission-gate-operator-fields">
          {session?.authenticated ? (
            <div className="submission-gate-operator-fields">
              <label>
                <span>Operator Name</span>
                <input value={safeText(session?.operator?.display_name, "Authenticated operator")} readOnly />
              </label>
              <label>
                <span>Operator Role</span>
                <input value={operatorRoleLabel(session?.operator?.role)} readOnly />
              </label>
            </div>
          ) : (
            <div className="submission-gate-auth-layout">
              <div className="submission-gate-operator-fields">
                <label>
                  <span>Operator ID</span>
                  <input value={authForm.operator_id} onChange={(event) => onAuthFormChange("operator_id", event.target.value)} placeholder="operator.admin" autoComplete="username" />
                </label>
                <label>
                  <span>Password</span>
                  <input type="password" value={authForm.password} onChange={(event) => onAuthFormChange("password", event.target.value)} placeholder="Operator password" autoComplete="current-password" />
                </label>
              </div>
              <div className="submission-gate-auth-actions">
                <button type="button" onClick={onAuthLogin} disabled={authLoading}>
                  <ShieldCheck size={15} />
                  {authLoading ? "Checking" : "Login"}
                </button>
              </div>
              <div className="submission-gate-operator-fields">
                <label>
                  <span>Bootstrap Admin ID</span>
                  <input value={authForm.bootstrap_operator_id} onChange={(event) => onAuthFormChange("bootstrap_operator_id", event.target.value)} placeholder="admin.local" autoComplete="username" />
                </label>
                <label>
                  <span>Bootstrap Display Name</span>
                  <input value={authForm.bootstrap_display_name} onChange={(event) => onAuthFormChange("bootstrap_display_name", event.target.value)} placeholder="LMCP Admin" />
                </label>
                <label className="wide">
                  <span>Bootstrap Password</span>
                  <input type="password" value={authForm.bootstrap_password} onChange={(event) => onAuthFormChange("bootstrap_password", event.target.value)} placeholder="Create initial admin password" autoComplete="new-password" />
                </label>
              </div>
              <div className="submission-gate-auth-actions">
                <button type="button" onClick={onAuthBootstrap} disabled={authLoading}>
                  <ShieldCheck size={15} />
                  Bootstrap Admin
                </button>
              </div>
            </div>
          )}
          <div className="submission-gate-operator-status">
            <p className="submission-risk warning">{operatorStatusMessage}</p>
            {authState?.error ? <p className="submission-risk blocker">{authState.error}</p> : null}
            <p className="submission-risk warning">Final submit remains disabled for every role. Manual submission only.</p>
            {session?.authenticated ? (
              <div className="submission-gate-auth-actions">
                <button type="button" onClick={onAuthLogout} disabled={authLoading}>
                  <LockKeyhole size={15} />
                  Logout
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <div className="submission-gate-archive-card">
        <div className="submission-gate-archive-head">
          <div>
            <h3>Compliance Archive</h3>
            <p>Immutable pack-local archive of the current compliance evidence set.</p>
          </div>
          <div className="submission-gate-archive-actions">
            <span className={`submission-gate-archive-badge ${statusTone(archiveBadgeStatus)}`}>
              <Archive size={13} />
              {safeText(archiveBadgeStatus, "unknown").replaceAll("_", " ")}
            </span>
            <button type="button" onClick={onComplianceArchiveCreateRequest} disabled={!packId || submissionComplianceArchiveState.loading || Boolean(archiveCreateBlockedReason)}>
              <Clock3 size={15} />
              {submissionComplianceArchiveState.loading ? "Working" : "Create Archive"}
            </button>
            <button type="button" onClick={onComplianceArchivesRequest} disabled={!packId || submissionComplianceArchiveState.loading}>
              <Clock3 size={15} />
              {submissionComplianceArchiveState.loading ? "Loading" : "Load Archives"}
            </button>
            <button type="button" onClick={() => onComplianceArchiveDownload("latest")} disabled={!packId || Boolean(archiveExportBlockedReason)}>
              <FileDown size={15} />
              Download Latest ZIP
            </button>
          </div>
        </div>
        {archiveCreateBlockedReason ? <div className="submission-gate-warning"><AlertTriangle size={15} />{archiveCreateBlockedReason}</div> : null}
        {archiveExportBlockedReason && archiveExportBlockedReason !== archiveCreateBlockedReason ? <div className="submission-gate-warning"><AlertTriangle size={15} />{archiveExportBlockedReason}</div> : null}
        {submissionComplianceArchiveState.error ? <div className="submission-gate-warning"><AlertTriangle size={15} />{submissionComplianceArchiveState.error}</div> : null}
        <div className="submission-gate-archive-summary">
          <div><span>Archive ID</span><b>{safeText(latestArchive?.archive_id, "Not loaded")}</b></div>
          <div><span>Created At</span><b>{safeText(latestArchive?.created_at, "Not loaded")}</b></div>
          <div><span>Archive Hash</span><b>{safeText(latestArchive?.archive_hash, "Not loaded")}</b></div>
          <div><span>Verification Status</span><b>{safeText(latestArchive?.verification_status, "unknown").replaceAll("_", " ")}</b></div>
          <div><span>File Count</span><b>{normalizeNumber(latestArchive?.file_count, 0)}</b></div>
          <div><span>Warnings</span><b>{normalizeNumber(latestArchive?.warnings?.length, archiveWarningCount)}</b></div>
        </div>
        <div className="submission-gate-archive-columns">
          <div>
            <h4>Latest Archive</h4>
            <div className="submission-risk-list">
              <p className={`submission-risk ${latestArchive ? "ok" : "warning"}`}>{latestArchive ? "Latest archive loaded locally." : "Load or create an archive to see the latest record."}</p>
              <p className="submission-risk warning">Final submit remains locked. Archives are evidence only.</p>
              <p className="submission-risk warning">Archive warning count: {archiveWarningCount}.</p>
              {latestArchiveWarnings.length ? latestArchiveWarnings.slice(0, 3).map((item, index) => (
                <p className="submission-risk warning" key={`archive-warning-${index}`}>{safeText(item)}</p>
              )) : null}
            </div>
          </div>
          <div>
            <h4>Latest 5 Archives ({archiveCount})</h4>
            <div className="submission-gate-archive-list">
              {(archives.slice(0, 5).length ? archives.slice(0, 5) : []).map((item) => (
                <div className="submission-gate-archive-item" key={safeText(item?.archive_id) || `archive-${safeText(item?.created_at)}`}>
                  <b>{safeText(item?.archive_id, "Archive")}</b>
                  <span>{safeText(item?.created_at, "Not loaded")} · {safeText(item?.verification_status, "unknown").replaceAll("_", " ")}</span>
                  <small>{safeText(item?.archive_hash, "Not loaded")}</small>
                  {packId && item?.archive_id ? (
                    <button type="button" onClick={() => onComplianceArchiveDownload(item.archive_id)} disabled={Boolean(archiveExportBlockedReason)}>
                      <FileDown size={13} />
                      Download ZIP
                    </button>
                  ) : null}
                </div>
              ))}
              {!archives.length ? <p className="submission-risk warning">No archives loaded yet.</p> : null}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
