import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Cpu,
  Filter,
  Globe2,
  LockKeyhole,
  PauseCircle,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";

const REQUEST_TIMEOUT_MS = 8000;

const WORKER_ENDPOINTS = [
  "/portal-submission/status",
  "/portal-submission/classify",
  "/etenders-session/status",
  "/v48-autonomous/status",
  "/v50-7-etenders-navigation/status",
  "/v50-7-promotion-gate/status",
  "/full-autonomous-cycle/status",
  "/system-stability/watchdog",
  "/health",
];

const SAFETY_LOCKS = ["controlled_dry_run_only", "no_portal_upload", "no_final_submit", "no_captcha_bypass"];
const DRAWER_TABS = ["Overview", "Session", "Current Task", "Events", "Blockers", "Reliability", "Safety"];

const DEMO_WORKERS = [
  {
    id: "demo-portal-worker",
    worker_name: "eTenders dry-run worker",
    portal: "eTenders",
    status: "Review Required",
    session_status: "Connected",
    current_task: "Controlled upload readiness dry-run",
    rfq_reference: "RFQ-WORKER-DEMO-001",
    browser_mode: "headed-review",
    dry_run_only: true,
    captcha_required: true,
    manual_intervention_required: true,
    last_seen: new Date(Date.now() - 12 * 60000).toISOString(),
    success_rate: 72,
    failure_count: 1,
    retry_pressure: "Medium",
    blockers: ["CAPTCHA/manual review required"],
    risks: ["Demo fallback data shown because live worker records did not load", "CAPTCHA bypass remains locked"],
    recommended_next_step: "Escalate manual intervention",
    events: [
      { type: "review_required", label: "Manual intervention required", timestamp: new Date(Date.now() - 12 * 60000).toISOString(), message: "CAPTCHA or portal confirmation needs an operator" },
      { type: "dry_run", label: "Controlled dry-run active", timestamp: new Date(Date.now() - 20 * 60000).toISOString(), message: "No portal upload or final submit is enabled" },
    ],
    _demo: true,
    _sources: ["frontend fallback"],
  },
];

function safeText(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return fallback;
}

function pick(obj, keys, fallback = undefined) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
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

function slug(value) {
  return safeText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function normalizeNumber(value, fallback = 0) {
  if (value === undefined || value === null || value === "") return fallback;
  const n = Number(String(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? n : fallback;
}

function normalizePercent(value, fallback = 0) {
  const n = normalizeNumber(value, fallback);
  if (n <= 1 && n > 0) return Math.round(n * 100);
  return Math.max(0, Math.min(100, Math.round(n)));
}

function normalizeBool(value, fallback = false) {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  const lower = safeText(value).toLowerCase();
  if (["true", "yes", "y", "1", "on", "required", "enabled"].includes(lower)) return true;
  if (["false", "no", "n", "0", "off", "none", "disabled"].includes(lower)) return false;
  return fallback;
}

function normalizeStatus(value, record = {}) {
  const raw = safeText(value || record.worker_status || record.session_status || record.state || record.health || record.status, "Unknown");
  const lower = raw.toLowerCase();
  if (lower.includes("captcha") || lower.includes("manual") || lower.includes("review")) return "Review Required";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("error") || lower.includes("crash")) return "Blocked";
  if (lower.includes("pause") || lower.includes("hold")) return "Paused";
  if (lower.includes("idle")) return "Idle";
  if (lower.includes("healthy") || lower.includes("online") || lower.includes("connected") || lower === "ok" || lower.includes("running")) return "Online";
  if (lower.includes("warn") || lower.includes("degraded")) return "Degraded";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeSessionStatus(value, record = {}) {
  const raw = safeText(value || record.browser_session || record.session || record.connection_status || record.status, "Unknown");
  const lower = raw.toLowerCase();
  if (lower.includes("connect") || lower.includes("active") || lower.includes("ready") || lower === "ok") return "Connected";
  if (lower.includes("expired") || lower.includes("login") || lower.includes("auth")) return "Auth Required";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("error")) return "Blocked";
  if (lower.includes("idle")) return "Idle";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizePortal(value, sourcePath = "") {
  const raw = safeText(value || sourcePath, "Portal");
  const lower = raw.toLowerCase();
  if (lower.includes("etender")) return "eTenders";
  if (lower.includes("cidb")) return "CIDB";
  if (lower.includes("treasury")) return "Treasury";
  if (lower.includes("municipal")) return "Municipal";
  if (lower.includes("soe")) return "SOE";
  if (lower.includes("portal-submission")) return "Portal Submission";
  if (lower.includes("health")) return "Backend";
  return raw.replace(/^\/+/, "").replaceAll("-", " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Portal";
}

function inferBrowserMode(record) {
  const explicit = safeText(pick(record, ["browser_mode", "mode", "automation_mode", "runner_mode", "playwright_mode"]));
  if (explicit) return explicit.replaceAll("_", "-");
  if (normalizeBool(record?.headless, false)) return "headless";
  if (normalizeBool(record?.headed, false)) return "headed";
  if (record?.browser || record?.page || record?.playwright) return "controlled";
  return "controlled";
}

function namedList(values) {
  return values
    .map((item) => {
      if (typeof item === "object") {
        return safeText(pick(item, ["name", "label", "field", "reason", "message", "error", "detail", "type", "status"]));
      }
      return safeText(item);
    })
    .filter(Boolean);
}

function containsAny(values, pattern) {
  return values.some((item) => pattern.test(safeText(item)));
}

function normalizeRetryPressure(value, failureCount = 0, retryCount = 0) {
  const raw = safeText(value);
  const lower = raw.toLowerCase();
  if (lower.includes("high") || lower.includes("critical")) return "High";
  if (lower.includes("medium") || lower.includes("warn")) return "Medium";
  if (lower.includes("low") || lower.includes("none")) return "Low";
  if (retryCount >= 5 || failureCount >= 3) return "High";
  if (retryCount >= 2 || failureCount >= 1) return "Medium";
  return "Low";
}

function normalizeEvent(value, fallbackType = "status") {
  if (typeof value === "string") {
    return { type: fallbackType, label: value, timestamp: "", message: value };
  }
  if (!value || typeof value !== "object") return null;
  const rawType = safeText(pick(value, ["type", "event", "state", "status", "level"]), fallbackType).toLowerCase();
  return {
    type: rawType.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || fallbackType,
    label: safeText(pick(value, ["label", "title", "event", "action", "status", "state"]), rawType.replaceAll("_", " ")),
    timestamp: safeText(pick(value, ["timestamp", "created_at", "updated_at", "last_seen", "time", "date"])),
    message: safeText(pick(value, ["message", "reason", "description", "detail", "error"]), ""),
  };
}

function isWorkerLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(worker|portal|session|browser|captcha|manual|intervention|automation|retry|watchdog|etender|submission|navigation|promotion|health|status|rfq|task|blocker|risk)/.test(keys);
}

function collectObjectRecords(payload, sourcePath) {
  const out = [];
  const seen = new Set();

  function walk(value, depth = 0) {
    if (depth > 5 || value === null || value === undefined) return;
    if (Array.isArray(value)) {
      value.forEach((item) => walk(item, depth + 1));
      return;
    }
    if (typeof value !== "object") return;

    if (isWorkerLike(value)) {
      const sig = `${sourcePath}:${safeText(pick(value, ["id", "worker_id", "session_id", "name", "worker_name", "portal", "status", "rfq_reference"]), JSON.stringify(Object.keys(value).slice(0, 14)))}`;
      if (!seen.has(sig)) {
        seen.add(sig);
        out.push({ ...value, _sourcePath: sourcePath });
      }
    }

    Object.entries(value).forEach(([childKey, childValue]) => {
      if (childKey.startsWith("_")) return;
      walk(childValue, depth + 1);
    });
  }

  walk(payload);
  return out;
}

function deriveLastSeen(record) {
  return safeText(
    pick(record, [
      "last_seen",
      "updated_at",
      "checked_at",
      "timestamp",
      "last_heartbeat",
      "heartbeat_at",
      "status_time",
      "created_at",
      "started_at",
    ]),
  );
}

function deriveEvents(record, worker) {
  const explicit = asArray(pick(record, ["events", "history", "recent_events", "event_feed", "logs", "timeline"]))
    .map((item) => normalizeEvent(item))
    .filter(Boolean);
  const inferred = [
    worker.last_seen && { type: "last_seen", label: "Worker last seen", timestamp: worker.last_seen, message: worker.status },
    worker.current_task && { type: "task", label: "Current task", timestamp: worker.last_seen, message: worker.current_task },
    worker.captcha_required && { type: "captcha", label: "CAPTCHA required", timestamp: worker.last_seen, message: "Operator review is required. CAPTCHA bypass is locked." },
    worker.manual_intervention_required && { type: "manual_intervention", label: "Manual intervention required", timestamp: worker.last_seen, message: worker.recommended_next_step },
  ].filter(Boolean);
  return uniqueBy([...explicit, ...inferred], (item) => `${item.type}:${item.timestamp}:${item.label}:${item.message}`.toLowerCase()).slice(0, 14);
}

function latestTimestamp(worker) {
  const values = [worker.last_seen, ...worker.events.map((item) => item.timestamp)].filter(Boolean);
  const times = values.map((item) => new Date(item).getTime()).filter(Number.isFinite);
  return times.length ? Math.max(...times) : 0;
}

function normalizeWorkerRecord(record, sourcePath) {
  const textDump = JSON.stringify(record || {}).toLowerCase();
  const baseBlockers = uniqueBy(namedList(asArray(pick(record, ["blockers", "blocking_reasons", "errors", "error", "hard_blockers", "manual_blockers"]))), (item) => item.toLowerCase());
  const baseRisks = uniqueBy(namedList(asArray(pick(record, ["risks", "risk_flags", "warnings", "alerts", "risk_notes"]))), (item) => item.toLowerCase());
  const captchaRequired =
    normalizeBool(pick(record, ["captcha_required", "captcha_detected", "requires_captcha", "manual_captcha"]), false) ||
    /captcha/.test(textDump) ||
    containsAny([...baseBlockers, ...baseRisks], /captcha/i);
  const manualInterventionRequired =
    normalizeBool(pick(record, ["manual_intervention_required", "requires_manual_intervention", "review_required", "operator_required"]), false) ||
    captchaRequired ||
    containsAny([...baseBlockers, ...baseRisks], /manual|intervention|operator|review/i);
  const failureCount = normalizeNumber(pick(record, ["failure_count", "failed_count", "errors_count", "error_count", "worker_crash_count", "failed_routers_count"]), baseBlockers.length);
  const retryCount = normalizeNumber(pick(record, ["retry_count", "retries", "attempts", "retry_attempts"]), 0);
  const dryRunOnly = normalizeBool(pick(record, ["dry_run_only", "dry_run", "controlled_dry_run_only", "no_final_submit"]), true);
  const workerName =
    safeText(pick(record, ["worker_name", "name", "worker", "service_name", "service", "component", "runner", "id", "worker_id"])) ||
    normalizePortal("", sourcePath);
  const portal = normalizePortal(pick(record, ["portal", "portal_name", "source", "submission_portal", "target_portal"]), sourcePath);
  const status = normalizeStatus(pick(record, ["status", "worker_status", "state", "health", "service_status"]), record);
  const sessionStatus = normalizeSessionStatus(pick(record, ["session_status", "browser_session", "session", "connection_status"]), record);
  const currentTask =
    safeText(pick(record, ["current_task", "task", "active_task", "last_action", "next_action", "status_message", "message", "description"])) ||
    (sourcePath.includes("health") ? "Backend health probe" : "Portal worker status probe");
  const rfqReference = safeText(pick(record, ["rfq_reference", "reference", "rfq_number", "buyer_rfq_number", "current_rfq", "rfq_id"]), "No RFQ assigned");
  const successRate = normalizePercent(pick(record, ["success_rate", "reliability_score", "health_score", "success_percent", "uptime_percent"]), status === "Online" ? 92 : 60);
  const retryPressure = normalizeRetryPressure(pick(record, ["retry_pressure", "pressure", "retry_status"]), failureCount, retryCount);
  const blockers = uniqueBy(
    [
      ...baseBlockers,
      captchaRequired && "CAPTCHA review required",
      manualInterventionRequired && "Manual intervention required",
      failureCount > 0 && `${failureCount} failure(s) recorded`,
    ].filter(Boolean),
    (item) => item.toLowerCase(),
  ).slice(0, 8);
  const risks = uniqueBy(
    [
      ...baseRisks,
      captchaRequired && "CAPTCHA bypass remains locked",
      !dryRunOnly && "Live mode reported by endpoint; frontend actions remain local only",
      retryPressure === "High" && "High retry pressure",
      status === "Blocked" && "Worker blocked",
    ].filter(Boolean),
    (item) => item.toLowerCase(),
  ).slice(0, 8);
  const recommendedNextStep =
    safeText(pick(record, ["recommended_next_step", "recommended_action", "next_action", "operator_action"])) ||
    (captchaRequired || manualInterventionRequired
      ? "Escalate manual intervention"
      : blockers.length
        ? "Mark needs review"
        : failureCount > 0
          ? "Clear local alert after review"
          : "Monitor worker");
  const id = slug(pick(record, ["id", "worker_id", "session_id", "record_id"], "") || `${workerName}-${portal}-${rfqReference}-${sourcePath}`) || `worker-${Math.random().toString(36).slice(2)}`;
  const worker = {
    id,
    worker_name: workerName,
    portal,
    status,
    session_status: sessionStatus,
    current_task: currentTask,
    rfq_reference: rfqReference,
    browser_mode: inferBrowserMode(record),
    dry_run_only: dryRunOnly,
    captcha_required: captchaRequired,
    manual_intervention_required: manualInterventionRequired,
    last_seen: deriveLastSeen(record),
    success_rate: successRate,
    failure_count: failureCount,
    retry_pressure: retryPressure,
    blockers,
    risks,
    recommended_next_step: recommendedNextStep,
    events: [],
    _sources: [sourcePath],
    _raw: record,
  };
  worker.events = deriveEvents(record, worker);
  return worker;
}

function mergeWorkers(records) {
  const map = new Map();
  for (const record of records) {
    const key = slug(record.worker_name !== "Portal" ? `${record.worker_name}-${record.portal}-${record.rfq_reference}` : record.id) || record.id;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, record);
      continue;
    }
    map.set(key, {
      ...existing,
      ...Object.fromEntries(Object.entries(record).filter(([, value]) => value !== "" && value !== undefined && value !== null)),
      id: existing.id,
      worker_name: existing.worker_name || record.worker_name,
      portal: existing.portal || record.portal,
      current_task: existing.current_task || record.current_task,
      rfq_reference: existing.rfq_reference !== "No RFQ assigned" ? existing.rfq_reference : record.rfq_reference,
      dry_run_only: existing.dry_run_only && record.dry_run_only,
      captcha_required: existing.captcha_required || record.captcha_required,
      manual_intervention_required: existing.manual_intervention_required || record.manual_intervention_required,
      success_rate: Math.max(existing.success_rate, record.success_rate),
      failure_count: Math.max(existing.failure_count, record.failure_count),
      retry_pressure: ["High", "Medium", "Low"].find((level) => [existing.retry_pressure, record.retry_pressure].includes(level)) || existing.retry_pressure,
      blockers: uniqueBy([...existing.blockers, ...record.blockers], (item) => item.toLowerCase()).slice(0, 8),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      events: uniqueBy([...existing.events, ...record.events], (item) => `${item.type}:${item.timestamp}:${item.label}`.toLowerCase()).slice(0, 14),
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => latestTimestamp(b) - latestTimestamp(a));
}

function statusTone(status) {
  const lower = safeText(status).toLowerCase();
  if (lower.includes("online") || lower.includes("connected") || lower.includes("healthy") || lower.includes("ok")) return "green";
  if (lower.includes("review") || lower.includes("manual") || lower.includes("captcha") || lower.includes("degraded") || lower.includes("paused") || lower.includes("idle")) return "amber";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("error") || lower.includes("crash")) return "red";
  return "neutral";
}

function pressureTone(value) {
  const lower = safeText(value).toLowerCase();
  if (lower.includes("high")) return "red";
  if (lower.includes("medium")) return "amber";
  if (lower.includes("low")) return "green";
  return "neutral";
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function recentMatch(worker, filter) {
  if (filter === "All") return true;
  const latest = latestTimestamp(worker);
  if (!latest) return false;
  const ageMs = Date.now() - latest;
  if (filter === "15m") return ageMs <= 15 * 60000;
  if (filter === "1h") return ageMs <= 3600000;
  if (filter === "24h") return ageMs <= 24 * 3600000;
  return true;
}

async function fetchEndpoint(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return { path, ok: true, data: await response.json() };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed" };
  } finally {
    clearTimeout(timeout);
  }
}

function StatusChip({ label, status, tone = statusTone(status) }) {
  return (
    <span className={`portal-worker-status-chip ${tone}`}>
      <small>{label}</small>
      <b>{status}</b>
    </span>
  );
}

function SafetyBanner() {
  return (
    <div className="portal-worker-safety-banner card">
      <div>
        <p className="eyebrow">Portal Worker Safety</p>
        <h2>Controlled Automation Monitor</h2>
        <p className="muted">This workspace monitors sessions only. It cannot upload to portals, bypass CAPTCHA, send email, or final submit.</p>
      </div>
      <div className="portal-worker-lock-grid">
        {SAFETY_LOCKS.map((lock) => (
          <span key={lock}>
            <LockKeyhole size={15} />
            {lock}
          </span>
        ))}
      </div>
    </div>
  );
}

function PanelShell({ title, icon: Icon, children }) {
  return (
    <div className="portal-worker-panel card">
      <div className="portal-worker-panel-head">
        <h3>{Icon ? <Icon size={16} /> : null}{title}</h3>
      </div>
      {children}
    </div>
  );
}

function WorkerEventFeed({ workers, onOpen }) {
  const events = workers
    .flatMap((worker) => worker.events.map((event, index) => ({ ...event, worker, key: `${worker.id}-${event.type}-${event.timestamp}-${index}` })))
    .sort((a, b) => (new Date(b.timestamp || 0).getTime() || 0) - (new Date(a.timestamp || 0).getTime() || 0))
    .slice(0, 28);

  if (!events.length) return <div className="portal-worker-empty-inline">No worker events available yet.</div>;

  return (
    <div className="portal-worker-event-feed">
      {events.map((event) => (
        <button type="button" key={event.key} onClick={() => onOpen(event.worker)}>
          <StatusChip label="Event" status={event.type.replaceAll("_", " ")} tone={statusTone(event.type)} />
          <div>
            <b>{event.label}</b>
            <span>{event.worker.worker_name} - {event.worker.portal}</span>
            <small>{formatDateTime(event.timestamp)}{event.message ? ` - ${event.message}` : ""}</small>
          </div>
        </button>
      ))}
    </div>
  );
}

function KeyValueGrid({ rows }) {
  return (
    <div className="portal-worker-health-grid">
      {rows.map((row, index) => (
        <div key={`${row.label}-${index}`}>
          <span>{row.label}</span>
          <b>{row.value}</b>
        </div>
      ))}
    </div>
  );
}

function RiskList({ items, empty, blocker = false }) {
  if (!items.length) return <div className="portal-worker-empty-inline">{empty}</div>;
  return (
    <div className="portal-worker-risk-list">
      {items.map((item, index) => <p className={`portal-worker-risk ${blocker ? "blocker" : ""}`} key={`${item}-${index}`}>{item}</p>)}
    </div>
  );
}

function DetailDrawer({ worker, activeTab, setActiveTab, onClose, operatorState, onOperatorAction }) {
  if (!worker) return null;
  const localDecision = operatorState[worker.id];

  return (
    <div className="portal-worker-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="portal-worker-drawer" aria-label="Portal worker detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="portal-worker-drawer-head">
          <div>
            <span className="portal-worker-kicker">{worker.portal}</span>
            <h2>{worker.worker_name}</h2>
            <p>{worker.rfq_reference} - {worker.browser_mode} - {formatDateTime(worker.last_seen)}</p>
          </div>
          <button className="portal-worker-icon-button" type="button" onClick={onClose} aria-label="Close worker detail">
            <X size={18} />
          </button>
        </div>

        <div className="portal-worker-scorebar">
          <StatusChip label="Worker" status={worker.status} />
          <StatusChip label="Session" status={worker.session_status} />
          <StatusChip label="Retry" status={worker.retry_pressure} tone={pressureTone(worker.retry_pressure)} />
          <StatusChip label="Dry-Run" status={worker.dry_run_only ? "Locked" : "Review"} tone={worker.dry_run_only ? "green" : "amber"} />
        </div>

        <div className="portal-worker-actions">
          <button type="button" onClick={() => onOperatorAction(worker.id, "Marked Needs Review")}><ShieldAlert size={15} />Mark Needs Review</button>
          <button type="button" onClick={() => onOperatorAction(worker.id, "Paused Worker Locally")}><PauseCircle size={15} />Pause Worker Locally</button>
          <button type="button" onClick={() => onOperatorAction(worker.id, "Cleared Local Alert")}><CheckCircle2 size={15} />Clear Local Alert</button>
          <button type="button" onClick={() => onOperatorAction(worker.id, "Escalated Manual Intervention")}><AlertTriangle size={15} />Escalate Manual Intervention</button>
        </div>
        {localDecision ? <div className="portal-worker-local-state">Local operator state: {localDecision}</div> : null}

        <div className="portal-worker-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="portal-worker-drawer-body">
          {activeTab === "Overview" ? (
            <div className="portal-worker-detail-grid">
              <div className="portal-worker-detail-card"><span>Status</span><b>{worker.status}</b></div>
              <div className="portal-worker-detail-card"><span>Portal</span><b>{worker.portal}</b></div>
              <div className="portal-worker-detail-card"><span>RFQ</span><b>{worker.rfq_reference}</b></div>
              <div className="portal-worker-detail-card"><span>Last Seen</span><b>{formatDateTime(worker.last_seen)}</b></div>
              <div className="portal-worker-detail-wide"><h3>Recommended Next Step</h3><p>{worker.recommended_next_step}</p></div>
            </div>
          ) : null}
          {activeTab === "Session" ? (
            <KeyValueGrid rows={[
              { label: "Session Status", value: worker.session_status },
              { label: "Browser Mode", value: worker.browser_mode },
              { label: "Dry-Run Only", value: worker.dry_run_only ? "Yes" : "Review" },
              { label: "Manual Intervention", value: worker.manual_intervention_required ? "Required" : "No" },
            ]} />
          ) : null}
          {activeTab === "Current Task" ? (
            <div className="portal-worker-detail-grid">
              <div className="portal-worker-detail-wide"><h3>Current Task</h3><p>{worker.current_task}</p></div>
              <div className="portal-worker-detail-card"><span>CAPTCHA</span><b>{worker.captcha_required ? "Required" : "No"}</b></div>
              <div className="portal-worker-detail-card"><span>Manual</span><b>{worker.manual_intervention_required ? "Required" : "No"}</b></div>
            </div>
          ) : null}
          {activeTab === "Events" ? <WorkerEventFeed workers={[worker]} onOpen={() => {}} /> : null}
          {activeTab === "Blockers" ? <RiskList items={worker.blockers} empty="No blockers detected." blocker /> : null}
          {activeTab === "Reliability" ? (
            <KeyValueGrid rows={[
              { label: "Success Rate", value: `${worker.success_rate}%` },
              { label: "Failure Count", value: worker.failure_count },
              { label: "Retry Pressure", value: worker.retry_pressure },
              { label: "Sources", value: worker._sources.join(", ") },
            ]} />
          ) : null}
          {activeTab === "Safety" ? (
            <>
              <div className="portal-worker-lock-grid detail">
                {SAFETY_LOCKS.map((lock) => (
                  <span key={lock}><LockKeyhole size={15} />{lock}</span>
                ))}
              </div>
              <p className="portal-worker-safety-note">Local review state only. This workspace cannot upload to portals, bypass CAPTCHA, send email, or perform final submit.</p>
            </>
          ) : null}
          {activeTab !== "Safety" ? <p className="portal-worker-safety-note">Local review state only. Safety locks remain enforced: {SAFETY_LOCKS.join(", ")}.</p> : null}
        </div>
      </aside>
    </div>
  );
}

export default function PortalWorkersWorkspace() {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], error: "" });
  const [workers, setWorkers] = useState([]);
  const [query, setQuery] = useState("");
  const [portal, setPortal] = useState("All");
  const [workerStatus, setWorkerStatus] = useState("All");
  const [dryRunOnly, setDryRunOnly] = useState("All");
  const [intervention, setIntervention] = useState("All");
  const [blockersOnly, setBlockersOnly] = useState(false);
  const [recentActivity, setRecentActivity] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadWorkers() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(WORKER_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeWorkerRecord(record, record._sourcePath));

      const merged = mergeWorkers(records).filter((worker) => worker.worker_name || worker.portal);
      setWorkers(merged.length ? merged : DEMO_WORKERS);
      setEndpointState({
        loading: false,
        results,
        error: results.some((result) => result.ok) ? "" : "No portal worker endpoints responded with usable data.",
      });
    }

    loadWorkers();
    return () => {
      cancelled = true;
    };
  }, []);

  const portals = useMemo(() => ["All", ...uniqueBy(workers.map((worker) => worker.portal), (item) => item).filter(Boolean)], [workers]);
  const statuses = useMemo(() => ["All", ...uniqueBy(workers.map((worker) => worker.status), (item) => item).filter(Boolean)], [workers]);
  const selectedWorker = useMemo(() => workers.find((worker) => worker.id === selectedId), [selectedId, workers]);

  const filteredWorkers = useMemo(() => {
    const term = query.trim().toLowerCase();
    return workers.filter((worker) => {
      const haystack = `${worker.worker_name} ${worker.portal} ${worker.status} ${worker.session_status} ${worker.current_task} ${worker.rfq_reference}`.toLowerCase();
      const dryRunMatch =
        dryRunOnly === "All" ||
        (dryRunOnly === "Dry-Run Only" && worker.dry_run_only) ||
        (dryRunOnly === "Review Live Mode" && !worker.dry_run_only);
      const interventionMatch =
        intervention === "All" ||
        (intervention === "CAPTCHA" && worker.captcha_required) ||
        (intervention === "Manual" && worker.manual_intervention_required) ||
        (intervention === "None" && !worker.captcha_required && !worker.manual_intervention_required);
      return (
        (!term || haystack.includes(term)) &&
        (portal === "All" || worker.portal === portal) &&
        (workerStatus === "All" || worker.status === workerStatus) &&
        dryRunMatch &&
        interventionMatch &&
        (!blockersOnly || worker.blockers.length > 0) &&
        recentMatch(worker, recentActivity)
      );
    });
  }, [blockersOnly, dryRunOnly, intervention, portal, query, recentActivity, workerStatus, workers]);

  const summary = useMemo(() => ({
    total: workers.length,
    online: workers.filter((worker) => statusTone(worker.status) === "green").length,
    intervention: workers.filter((worker) => worker.captcha_required || worker.manual_intervention_required).length,
    blocked: workers.filter((worker) => worker.blockers.length > 0 || statusTone(worker.status) === "red").length,
  }), [workers]);

  const focusedWorker = selectedWorker || filteredWorkers[0] || workers[0] || DEMO_WORKERS[0];
  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = workers.some((worker) => worker._demo);
  const etendersWorker = workers.find((worker) => worker.portal === "eTenders") || focusedWorker;
  const manualQueue = filteredWorkers.filter((worker) => worker.captcha_required || worker.manual_intervention_required);
  const failureQueue = filteredWorkers.filter((worker) => worker.failure_count > 0 || worker.retry_pressure !== "Low");
  const portalCompatibility = useMemo(() => {
    const map = new Map();
    workers.forEach((worker) => {
      const current = map.get(worker.portal) || { portal: worker.portal, total: 0, online: 0, blocked: 0, intervention: 0 };
      current.total += 1;
      if (statusTone(worker.status) === "green") current.online += 1;
      if (statusTone(worker.status) === "red" || worker.blockers.length) current.blocked += 1;
      if (worker.captcha_required || worker.manual_intervention_required) current.intervention += 1;
      map.set(worker.portal, current);
    });
    return [...map.values()];
  }, [workers]);

  function openWorker(worker) {
    setSelectedId(worker.id);
    setActiveTab("Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  return (
    <section className="portal-workers-workspace" id="portal-workers-workspace">
      <SafetyBanner />

      <div className="portal-worker-hero card">
        <div>
          <p className="eyebrow">Portal Workers</p>
          <h1>Portal Workers Workspace</h1>
          <p className="muted">Read-only worker and browser-session monitor probing {API_BASE}. Operator controls update local browser state only.</p>
        </div>
        <div className="portal-worker-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${WORKER_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="portal-worker-summary-grid">
        <div className="portal-worker-summary-card"><span>Workers / Sessions</span><b>{summary.total}</b></div>
        <div className="portal-worker-summary-card good"><span>Online</span><b>{summary.online}</b></div>
        <div className="portal-worker-summary-card amber"><span>CAPTCHA / Manual</span><b>{summary.intervention}</b></div>
        <div className="portal-worker-summary-card bad"><span>Blocked / Risk</span><b>{summary.blocked}</b></div>
      </div>

      <div className="portal-worker-toolbar card">
        <label className="portal-worker-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search worker, portal, RFQ, task" />
        </label>
        <label><Filter size={15} /><select value={portal} onChange={(event) => setPortal(event.target.value)}>{portals.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={workerStatus} onChange={(event) => setWorkerStatus(event.target.value)}>{statuses.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={dryRunOnly} onChange={(event) => setDryRunOnly(event.target.value)}>{["All", "Dry-Run Only", "Review Live Mode"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={intervention} onChange={(event) => setIntervention(event.target.value)}>{["All", "CAPTCHA", "Manual", "None"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={recentActivity} onChange={(event) => setRecentActivity(event.target.value)}>{["All", "15m", "1h", "24h"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <button className={blockersOnly ? "active" : ""} type="button" onClick={() => setBlockersOnly((value) => !value)}><ShieldAlert size={15} />Blockers only</button>
      </div>

      {endpointState.error ? <div className="portal-worker-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="portal-worker-warning"><Cpu size={16} />No live portal worker rows were found. Showing a non-destructive workspace preview row.</div> : null}

      <div className="portal-worker-table-card card">
        <div className="card-head">
          <h2>Active Worker Table</h2>
          <span>{filteredWorkers.length} visible</span>
        </div>
        <div className="portal-worker-table-scroll">
          <table className="portal-worker-table">
            <thead>
              <tr>
                <th>Worker</th>
                <th>Portal</th>
                <th>Status</th>
                <th>Session</th>
                <th>Task</th>
                <th>Safety</th>
                <th>Reliability</th>
                <th>Last Seen</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredWorkers.map((worker, index) => (
                <tr key={`${worker.id}-${index}`} onClick={() => openWorker(worker)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openWorker(worker)}>
                  <td><b>{worker.worker_name}</b><span>{worker.rfq_reference}</span></td>
                  <td>{worker.portal}</td>
                  <td><StatusChip label="Worker" status={worker.status} /></td>
                  <td><StatusChip label="Session" status={worker.session_status} /></td>
                  <td><span className="portal-worker-task">{worker.current_task}</span></td>
                  <td>
                    <div className="portal-worker-safety-mini">
                      <span>{worker.dry_run_only ? "dry-run" : "review"}</span>
                      {worker.captcha_required ? <span>captcha</span> : null}
                      {worker.manual_intervention_required ? <span>manual</span> : null}
                    </div>
                  </td>
                  <td><StatusChip label={`${worker.success_rate}%`} status={worker.retry_pressure} tone={pressureTone(worker.retry_pressure)} /></td>
                  <td>{formatDateTime(worker.last_seen)}</td>
                  <td><button className="portal-worker-row-button" type="button" onClick={(event) => { event.stopPropagation(); openWorker(worker); }}>Open</button></td>
                </tr>
              ))}
              {!filteredWorkers.length ? (
                <tr><td colSpan="9"><div className="portal-worker-empty-inline">No workers match the current filters.</div></td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="portal-worker-panels">
        <PanelShell title="eTenders Session Health" icon={Globe2}>
          <KeyValueGrid rows={[
            { label: "Worker", value: etendersWorker.worker_name },
            { label: "Session", value: etendersWorker.session_status },
            { label: "Status", value: etendersWorker.status },
            { label: "Last Seen", value: formatDateTime(etendersWorker.last_seen) },
          ]} />
        </PanelShell>

        <PanelShell title="Browser/Automation Status" icon={Activity}>
          <KeyValueGrid rows={[
            { label: "Browser Mode", value: focusedWorker.browser_mode },
            { label: "Dry-Run Only", value: focusedWorker.dry_run_only ? "Locked" : "Review" },
            { label: "Portal Upload", value: "Locked" },
            { label: "Final Submit", value: "Locked" },
          ]} />
        </PanelShell>

        <PanelShell title="CAPTCHA / Manual Intervention Queue" icon={ShieldAlert}>
          <div className="portal-worker-queue-list">
            {manualQueue.slice(0, 10).map((worker, index) => (
              <button type="button" key={`${worker.id}-manual-${index}`} onClick={() => openWorker(worker)}>
                <StatusChip label={worker.captcha_required ? "CAPTCHA" : "Manual"} status="Review Required" />
                <div><b>{worker.worker_name}</b><span>{worker.portal} - {worker.recommended_next_step}</span></div>
              </button>
            ))}
            {!manualQueue.length ? <div className="portal-worker-empty-inline">No CAPTCHA or manual intervention queue items.</div> : null}
          </div>
        </PanelShell>

        <PanelShell title="Retry Pressure & Failure Panel" icon={Clock3}>
          <div className="portal-worker-queue-list">
            {failureQueue.slice(0, 10).map((worker, index) => (
              <button type="button" key={`${worker.id}-failure-${index}`} onClick={() => openWorker(worker)}>
                <StatusChip label="Retry" status={worker.retry_pressure} tone={pressureTone(worker.retry_pressure)} />
                <div><b>{worker.worker_name}</b><span>{worker.failure_count} failure(s) - {worker.success_rate}% success</span></div>
              </button>
            ))}
            {!failureQueue.length ? <div className="portal-worker-empty-inline">No elevated retry pressure detected.</div> : null}
          </div>
        </PanelShell>

        <PanelShell title="Portal Compatibility" icon={ShieldCheck}>
          <div className="portal-worker-compat-list">
            {portalCompatibility.map((row, index) => (
              <div key={`${row.portal}-${index}`}>
                <b>{row.portal}</b>
                <span>{row.online}/{row.total} online</span>
                <StatusChip label="Review" status={row.blocked || row.intervention ? "Attention" : "Compatible"} tone={row.blocked ? "red" : row.intervention ? "amber" : "green"} />
              </div>
            ))}
          </div>
        </PanelShell>

        <PanelShell title="Worker Event Feed" icon={Cpu}>
          <WorkerEventFeed workers={filteredWorkers} onOpen={openWorker} />
        </PanelShell>
      </div>

      <DetailDrawer
        worker={selectedWorker}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
      />
    </section>
  );
}
