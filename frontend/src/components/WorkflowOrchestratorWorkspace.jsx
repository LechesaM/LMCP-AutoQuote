import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Cpu,
  Filter,
  Gauge,
  GitBranch,
  History,
  PauseCircle,
  Repeat2,
  Search,
  ShieldAlert,
  TrendingUp,
  UserCog,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";

const REQUEST_TIMEOUT_MS = 8000;
const HIGH_PROFIT_THRESHOLD = 30000;

const WORKFLOW_ENDPOINTS = [
  "/rfq-lifecycle/status",
  "/submission-history/recent",
  "/submission-proof/status",
  "/health",
  "/workers/status",
  "/telemetry",
  "/metrics",
];

const STAGES = [
  "harvested",
  "parsing",
  "qualification",
  "pricing",
  "proof",
  "review",
  "submission_ready",
  "blocked",
  "completed",
];

const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
const DRAWER_TABS = ["Lifecycle", "Risks", "Proof", "Worker", "Retry History", "Escalations", "Audit"];

const DEMO_WORKFLOWS = [
  {
    rfq_id: "RFQ-WF-DEMO-001",
    buyer: "Demo Buyer",
    province: "GP",
    current_stage: "review",
    next_stage: "submission_ready",
    readiness_score: 78,
    orchestration_status: "Simulation Review",
    blockers: ["Manual approval required before upload dry-run review"],
    risks: ["Demo fallback data shown because live workflow rows did not load"],
    worker_assignment: "orchestrator-review-worker",
    retry_pressure: "Medium",
    proof_status: "Pending",
    estimated_profit: 42500,
    escalation_required: true,
    recommended_action: "Escalate Review",
    title: "Controlled workflow orchestration preview",
    timeline: [
      { stage: "harvested", label: "RFQ harvested", timestamp: new Date(Date.now() - 6 * 3600000).toISOString(), detail: "Discovery completed" },
      { stage: "parsing", label: "Documents parsed", timestamp: new Date(Date.now() - 4 * 3600000).toISOString(), detail: "Returnables extracted" },
      { stage: "review", label: "Manual review required", timestamp: new Date(Date.now() - 45 * 60000).toISOString(), detail: "Simulation-only gate active" },
    ],
    retry_history: [{ label: "Controlled retry check", count: 1, timestamp: new Date(Date.now() - 30 * 60000).toISOString() }],
    audit: ["Simulation Mode Only — No Real Submission Execution", "No portal upload, email send, or final submit path is exposed"],
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

function normalizeScore(value, fallback = 0) {
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

function normalizeProvince(value) {
  const raw = safeText(value, "Unknown").toUpperCase();
  if (raw.includes("GAUTENG") || raw === "GP") return "GP";
  if (raw.includes("FREE STATE") || raw === "FS") return "FS";
  if (raw.includes("KWAZULU") || raw.includes("KZN")) return "KZN";
  if (raw.includes("WESTERN CAPE") || raw === "WC") return "WC";
  if (raw.includes("EASTERN CAPE") || raw === "EC") return "EC";
  if (raw.includes("NORTHERN CAPE") || raw === "NC") return "NC";
  if (raw.includes("NORTH WEST") || raw === "NW") return "NW";
  if (raw.includes("MPUMALANGA") || raw === "MP") return "MP";
  if (raw.includes("LIMPOPO") || raw === "LP") return "LP";
  return raw && raw !== "UNKNOWN" ? raw.slice(0, 18) : "Unknown";
}

function normalizeStage(value, fallback = "harvested") {
  const lower = safeText(value, fallback).toLowerCase().replaceAll("-", "_");
  if (lower.includes("complete") || lower.includes("submitted") || lower.includes("proof_captured")) return "completed";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("reject")) return "blocked";
  if (lower.includes("submission_ready") || (lower.includes("ready") && lower.includes("submit"))) return "submission_ready";
  if (lower.includes("proof") || lower.includes("receipt")) return "proof";
  if (lower.includes("review") || lower.includes("manual") || lower.includes("escalat")) return "review";
  if (lower.includes("price") || lower.includes("quote") || lower.includes("boq")) return "pricing";
  if (lower.includes("qual") || lower.includes("eligible") || lower.includes("score")) return "qualification";
  if (lower.includes("parse") || lower.includes("document") || lower.includes("returnable")) return "parsing";
  if (lower.includes("harvest") || lower.includes("discover") || lower.includes("new")) return "harvested";
  return STAGES.includes(lower) ? lower : fallback;
}

function inferNextStage(stage) {
  if (stage === "blocked" || stage === "completed") return stage;
  const index = STAGES.indexOf(stage);
  if (index < 0) return "review";
  const next = STAGES[index + 1];
  return next && next !== "blocked" ? next : "completed";
}

function normalizeOrchestrationStatus(value, stage, blockers = []) {
  const raw = safeText(value);
  const lower = raw.toLowerCase();
  if (blockers.length || stage === "blocked" || lower.includes("block") || lower.includes("fail")) return "Blocked";
  if (lower.includes("escal") || lower.includes("review") || stage === "review") return "Review Required";
  if (lower.includes("ready") || stage === "submission_ready") return "Ready";
  if (lower.includes("complete") || stage === "completed") return "Completed";
  if (lower.includes("run") || lower.includes("active") || lower.includes("progress")) return "Active";
  return raw ? raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Simulated";
}

function normalizeProofStatus(value, present = false) {
  const raw = safeText(value, present ? "Ready" : "Pending");
  const lower = raw.toLowerCase();
  if (lower.includes("verified") || lower.includes("captured") || lower.includes("generated") || lower.includes("ready")) return "Ready";
  if (lower.includes("review") || lower.includes("pending")) return "Pending";
  if (lower.includes("missing") || lower.includes("fail") || lower.includes("block")) return "Blocked";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

function normalizeRetryPressure(value, retryCount = 0, failureCount = 0) {
  const lower = safeText(value).toLowerCase();
  if (lower.includes("critical") || lower.includes("high")) return "High";
  if (lower.includes("medium") || lower.includes("warn")) return "Medium";
  if (lower.includes("low") || lower.includes("none")) return "Low";
  if (retryCount >= 5 || failureCount >= 3) return "High";
  if (retryCount >= 2 || failureCount >= 1) return "Medium";
  return "Low";
}

function retryTone(value) {
  const lower = safeText(value).toLowerCase();
  if (lower.includes("high")) return "red";
  if (lower.includes("medium")) return "amber";
  if (lower.includes("low")) return "green";
  return "neutral";
}

function statusTone(value) {
  const lower = safeText(value).toLowerCase();
  if (lower.includes("ready") || lower.includes("complete") || lower.includes("active")) return "green";
  if (lower.includes("review") || lower.includes("pending") || lower.includes("simulat")) return "amber";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("risk")) return "red";
  return "neutral";
}

function scoreTone(score) {
  if (score >= 80) return "green";
  if (score >= 50) return "amber";
  return "red";
}

function stageLabel(stage) {
  return safeText(stage).replaceAll("_", " ");
}

function money(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(n);
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function normalizeTimelineEvent(value, fallbackStage = "harvested") {
  if (typeof value === "string") {
    return { stage: normalizeStage(value, fallbackStage), label: value, timestamp: "", detail: value };
  }
  if (!value || typeof value !== "object") return null;
  const stage = normalizeStage(pick(value, ["stage", "state", "to_state", "status", "event", "type"]), fallbackStage);
  return {
    stage,
    label: safeText(pick(value, ["label", "title", "event", "action", "status", "state"]), stageLabel(stage)),
    timestamp: safeText(pick(value, ["timestamp", "created_at", "updated_at", "time", "date", "submitted_at"])),
    detail: safeText(pick(value, ["detail", "message", "reason", "description"]), ""),
  };
}

function normalizeRetryEvent(value, fallbackCount = 0) {
  if (typeof value === "string") {
    return { label: value, count: fallbackCount, timestamp: "", detail: value };
  }
  if (!value || typeof value !== "object") return null;
  return {
    label: safeText(pick(value, ["label", "name", "event", "reason", "status"]), "Retry event"),
    count: normalizeNumber(pick(value, ["count", "retry_count", "attempts", "retries"]), fallbackCount),
    timestamp: safeText(pick(value, ["timestamp", "created_at", "updated_at", "time", "date"])),
    detail: safeText(pick(value, ["detail", "message", "error", "description"]), ""),
  };
}

function isWorkflowLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(rfq|tender|lifecycle|stage|buyer|province|worker|retry|proof|profit|submission|orchestration|blocker|risk|pipeline|readiness|qualification|pricing|harvest|parse|quote)/.test(keys);
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

    if (isWorkflowLike(value)) {
      const sig = `${sourcePath}:${safeText(pick(value, ["id", "rfq_id", "reference", "rfq_number", "buyer_rfq_number", "title", "buyer", "stage"]), JSON.stringify(Object.keys(value).slice(0, 14)))}`;
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

function deriveTimeline(record, currentStage) {
  const explicit = asArray(pick(record, ["timeline", "events", "history", "lifecycle_timeline", "stage_history"]))
    .map((item) => normalizeTimelineEvent(item, currentStage))
    .filter(Boolean);
  if (explicit.length) {
    return uniqueBy(explicit, (item) => `${item.stage}:${item.timestamp}:${item.label}`.toLowerCase()).slice(0, 12);
  }
  const currentIndex = Math.max(0, STAGES.indexOf(currentStage));
  return STAGES
    .filter((stage) => stage !== "blocked")
    .slice(0, Math.min(currentIndex + 1, 8))
    .map((stage) => ({ stage, label: `${stageLabel(stage)} stage`, timestamp: "", detail: stage === currentStage ? "Current lifecycle stage" : "Prior lifecycle stage" }));
}

function deriveReadiness(record, stage, blockers) {
  const explicit = pick(record, ["readiness_score", "orchestration_readiness_score", "submission_readiness_score", "quote_readiness_score", "score"]);
  if (explicit !== undefined) return normalizeScore(explicit, 0);
  const baseByStage = {
    harvested: 35,
    parsing: 45,
    qualification: 58,
    pricing: 68,
    proof: 76,
    review: 72,
    submission_ready: 88,
    blocked: 32,
    completed: 100,
  };
  return Math.max(0, Math.min(100, (baseByStage[stage] || 50) - blockers.length * 8));
}

function normalizeWorkflowRecord(record, sourcePath) {
  const rfqId = safeText(
    pick(record, ["rfq_id", "id", "record_id", "rfq_reference", "reference", "rfq_number", "buyer_rfq_number", "tender_number", "bid_number"]),
    "RFQ",
  );
  const buyer = safeText(pick(record, ["buyer", "buyer_name", "department", "organisation", "organization", "client", "entity"]), "Unknown Buyer");
  const province = normalizeProvince(pick(record, ["province", "buyer_province", "region", "location"]));
  const title = safeText(pick(record, ["title", "description", "name", "opportunity_title", "tender_title", "subject"]), rfqId);
  const currentStage = normalizeStage(pick(record, ["current_stage", "lifecycle_state", "stage", "status", "pipeline_status", "state", "submission_status"]));
  const nextStage = normalizeStage(pick(record, ["next_stage", "target_stage", "recommended_stage"]), inferNextStage(currentStage));
  const retryCount = normalizeNumber(pick(record, ["retry_count", "retries", "attempts", "retry_attempts"]), 0);
  const failureCount = normalizeNumber(pick(record, ["failure_count", "failed_count", "errors_count", "error_count"]), 0);
  const retryPressure = normalizeRetryPressure(pick(record, ["retry_pressure", "pressure", "retry_status"]), retryCount, failureCount);
  const blockers = uniqueBy(
    [
      ...namedList(asArray(pick(record, ["blockers", "blocking_reasons", "errors", "error", "hard_blockers", "missing_items"]))),
      currentStage === "blocked" && "Lifecycle stage blocked",
      failureCount > 0 && `${failureCount} failure(s) recorded`,
    ].filter(Boolean),
    (item) => item.toLowerCase(),
  ).slice(0, 8);
  const readinessScore = deriveReadiness(record, currentStage, blockers);
  const proofStatus = normalizeProofStatus(pick(record, ["proof_status", "submission_proof_status", "verification_status"]), currentStage === "proof" || currentStage === "completed");
  const risks = uniqueBy(
    [
      ...namedList(asArray(pick(record, ["risks", "risk_flags", "warnings", "alerts", "risk_notes"]))),
      retryPressure === "High" && "High retry pressure",
      readinessScore < 50 && "Low orchestration readiness",
      proofStatus === "Blocked" && "Proof status blocked",
    ].filter(Boolean),
    (item) => item.toLowerCase(),
  ).slice(0, 8);
  const escalationRequired =
    normalizeBool(pick(record, ["escalation_required", "requires_escalation", "review_required", "manual_intervention_required"]), false) ||
    blockers.length > 0 ||
    retryPressure === "High" ||
    currentStage === "blocked" ||
    currentStage === "review";
  const orchestrationStatus = normalizeOrchestrationStatus(
    pick(record, ["orchestration_status", "workflow_status", "status", "state", "pipeline_status"]),
    currentStage,
    blockers,
  );
  const workerAssignment =
    safeText(pick(record, ["worker_assignment", "assigned_worker", "worker_name", "worker", "service_name", "owner", "assignee"])) ||
    (currentStage === "blocked" ? "review-worker" : `${currentStage}-worker`);
  const estimatedProfit = normalizeNumber(pick(record, ["estimated_profit", "total_profit", "profit", "margin_value", "expected_profit"]), 0);
  const recommendedAction =
    safeText(pick(record, ["recommended_action", "recommended_next_step", "next_action", "operator_action"])) ||
    (escalationRequired ? "Escalate Review" : readinessScore >= 80 ? "Simulate Advance Stage" : "Hold Workflow");
  const timeline = deriveTimeline(record, currentStage);
  const retryHistory = uniqueBy(
    asArray(pick(record, ["retry_history", "retries", "retry_events", "failure_history"]))
      .map((item) => normalizeRetryEvent(item, retryCount))
      .filter(Boolean),
    (item) => `${item.label}:${item.timestamp}:${item.count}`.toLowerCase(),
  );
  const audit = uniqueBy(
    [
      ...namedList(asArray(pick(record, ["audit", "audit_log", "audit_flags", "notes"]))),
      `Source: ${sourcePath}`,
      "Simulation Mode Only — No Real Submission Execution",
    ],
    (item) => item.toLowerCase(),
  ).slice(0, 8);

  return {
    rfq_id: rfqId,
    buyer,
    province,
    current_stage: currentStage,
    next_stage: nextStage,
    readiness_score: readinessScore,
    orchestration_status: orchestrationStatus,
    blockers,
    risks,
    worker_assignment: workerAssignment,
    retry_pressure: retryPressure,
    proof_status: proofStatus,
    estimated_profit: estimatedProfit,
    escalation_required: escalationRequired,
    recommended_action: recommendedAction,
    title,
    timeline,
    retry_history: retryHistory,
    audit,
    _sources: [sourcePath],
    _raw: record,
  };
}

function latestTimestamp(workflow) {
  const values = [
    ...workflow.timeline.map((item) => item.timestamp),
    ...workflow.retry_history.map((item) => item.timestamp),
  ].filter(Boolean);
  const times = values.map((item) => new Date(item).getTime()).filter(Number.isFinite);
  return times.length ? Math.max(...times) : 0;
}

function mergeWorkflows(records) {
  const map = new Map();
  for (const record of records) {
    const key = slug(record.rfq_id !== "RFQ" ? record.rfq_id : `${record.buyer}-${record.title}-${record.current_stage}`) || record.rfq_id;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, record);
      continue;
    }
    map.set(key, {
      ...existing,
      ...Object.fromEntries(Object.entries(record).filter(([, value]) => value !== "" && value !== undefined && value !== null)),
      rfq_id: existing.rfq_id !== "RFQ" ? existing.rfq_id : record.rfq_id,
      buyer: existing.buyer !== "Unknown Buyer" ? existing.buyer : record.buyer,
      province: existing.province !== "Unknown" ? existing.province : record.province,
      readiness_score: Math.max(existing.readiness_score, record.readiness_score),
      estimated_profit: Math.max(existing.estimated_profit, record.estimated_profit),
      blockers: uniqueBy([...existing.blockers, ...record.blockers], (item) => item.toLowerCase()).slice(0, 8),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      escalation_required: existing.escalation_required || record.escalation_required,
      timeline: uniqueBy([...existing.timeline, ...record.timeline], (item) => `${item.stage}:${item.timestamp}:${item.label}`.toLowerCase()).slice(0, 12),
      retry_history: uniqueBy([...existing.retry_history, ...record.retry_history], (item) => `${item.label}:${item.timestamp}:${item.count}`.toLowerCase()).slice(0, 10),
      audit: uniqueBy([...existing.audit, ...record.audit], (item) => item.toLowerCase()).slice(0, 8),
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => latestTimestamp(b) - latestTimestamp(a));
}

async function fetchEndpoint(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { message: text };
    }
    return { path, ok: true, data };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed" };
  } finally {
    clearTimeout(timeout);
  }
}

function StageChip({ stage }) {
  return <span className={`workflow-orchestrator-stage-chip stage-${stage}`}>{stageLabel(stage)}</span>;
}

function StatusChip({ label, status, tone = statusTone(status) }) {
  return (
    <span className={`workflow-orchestrator-status-chip ${tone}`}>
      <small>{label}</small>
      <b>{status}</b>
    </span>
  );
}

function ReadinessGauge({ score, label }) {
  const safe = Math.max(0, Math.min(100, Number(score || 0)));
  return (
    <div className={`workflow-orchestrator-gauge ${scoreTone(safe)}`} style={{ background: `conic-gradient(#18e6a6 ${safe}%, rgba(255,255,255,.12) 0)` }}>
      <div>
        <b>{safe}</b>
        <span>{label}</span>
      </div>
    </div>
  );
}

function TrendLine({ values = [] }) {
  const safe = values.length ? values : [1, 2, 1, 3, 2, 4, 3];
  const max = Math.max(...safe, 1);
  const points = safe.map((value, index) => `${(index / Math.max(1, safe.length - 1)) * 100},${42 - (value / max) * 34}`).join(" ");
  return (
    <svg className="workflow-orchestrator-trend" viewBox="0 0 100 46" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}

function HeatBar({ value, label }) {
  const tone = retryTone(value);
  const width = value === "High" ? 92 : value === "Medium" ? 58 : 28;
  return (
    <div className="workflow-orchestrator-heatbar">
      <span>{label}</span>
      <div><i className={tone} style={{ width: `${width}%` }} /></div>
      <b>{value}</b>
    </div>
  );
}

function PanelShell({ title, icon: Icon, children }) {
  return (
    <div className="workflow-orchestrator-panel card">
      <div className="workflow-orchestrator-panel-head">
        <h3>{Icon ? <Icon size={16} /> : null}{title}</h3>
      </div>
      {children}
    </div>
  );
}

function RiskList({ items, empty, blocker = false }) {
  if (!items.length) return <div className="workflow-orchestrator-empty-inline">{empty}</div>;
  return (
    <div className="workflow-orchestrator-risk-list">
      {items.map((item, index) => <p className={`workflow-orchestrator-risk ${blocker ? "blocker" : ""}`} key={`${item}-${index}`}>{item}</p>)}
    </div>
  );
}

function TimelineList({ timeline }) {
  if (!timeline.length) return <div className="workflow-orchestrator-empty-inline">No lifecycle timeline events available.</div>;
  return (
    <div className="workflow-orchestrator-timeline">
      {timeline.map((event, index) => (
        <div key={`${event.stage}-${event.timestamp}-${index}`}>
          <StageChip stage={event.stage} />
          <b>{event.label}</b>
          <span>{formatDateTime(event.timestamp)}</span>
          {event.detail ? <small>{event.detail}</small> : null}
        </div>
      ))}
    </div>
  );
}

function DetailDrawer({ workflow, activeTab, setActiveTab, onClose, operatorState, onOperatorAction }) {
  if (!workflow) return null;
  const localDecision = operatorState[workflow.rfq_id];

  return (
    <div className="workflow-orchestrator-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="workflow-orchestrator-drawer" aria-label="Workflow orchestration detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="workflow-orchestrator-drawer-head">
          <div>
            <span className="workflow-orchestrator-kicker">{workflow.rfq_id}</span>
            <h2>{workflow.title}</h2>
            <p>{workflow.buyer} - {workflow.province} - {money(workflow.estimated_profit)}</p>
          </div>
          <button className="workflow-orchestrator-icon-button" type="button" onClick={onClose} aria-label="Close workflow detail">
            <X size={18} />
          </button>
        </div>

        <div className="workflow-orchestrator-scorebar">
          <StageChip stage={workflow.current_stage} />
          <StatusChip label="Status" status={workflow.orchestration_status} />
          <StatusChip label="Retry" status={workflow.retry_pressure} tone={retryTone(workflow.retry_pressure)} />
          <ReadinessGauge score={workflow.readiness_score} label="ready" />
        </div>

        <div className="workflow-orchestrator-actions">
          <button type="button" onClick={() => onOperatorAction(workflow.rfq_id, "Simulated Advance Stage")}><ArrowRight size={15} />Simulate Advance Stage</button>
          <button type="button" onClick={() => onOperatorAction(workflow.rfq_id, "Workflow Held")}><PauseCircle size={15} />Hold Workflow</button>
          <button type="button" onClick={() => onOperatorAction(workflow.rfq_id, "Escalated Review")}><ShieldAlert size={15} />Escalate Review</button>
          <button type="button" onClick={() => onOperatorAction(workflow.rfq_id, "Worker Reassignment Simulated")}><UserCog size={15} />Reassign Worker</button>
          <button type="button" onClick={() => onOperatorAction(workflow.rfq_id, "Marked Manual Intervention")}><AlertTriangle size={15} />Mark Manual Intervention</button>
        </div>
        {localDecision ? <div className="workflow-orchestrator-local-state">Local simulation state: {localDecision}</div> : null}

        <div className="workflow-orchestrator-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="workflow-orchestrator-drawer-body">
          {activeTab === "Lifecycle" ? <TimelineList timeline={workflow.timeline} /> : null}
          {activeTab === "Risks" ? (
            <>
              <RiskList items={workflow.blockers} empty="No blockers detected." blocker />
              <RiskList items={workflow.risks} empty="No risks detected." />
            </>
          ) : null}
          {activeTab === "Proof" ? (
            <div className="workflow-orchestrator-detail-grid">
              <div className="workflow-orchestrator-detail-card"><span>Proof Status</span><b>{workflow.proof_status}</b></div>
              <div className="workflow-orchestrator-detail-card"><span>Current Stage</span><b>{stageLabel(workflow.current_stage)}</b></div>
              <div className="workflow-orchestrator-detail-wide"><h3>Proof Gate</h3><p>Proof data is read-only. This workspace cannot upload, submit, or create proof artifacts.</p></div>
            </div>
          ) : null}
          {activeTab === "Worker" ? (
            <div className="workflow-orchestrator-detail-grid">
              <div className="workflow-orchestrator-detail-card"><span>Assignment</span><b>{workflow.worker_assignment}</b></div>
              <div className="workflow-orchestrator-detail-card"><span>Next Stage</span><b>{stageLabel(workflow.next_stage)}</b></div>
              <div className="workflow-orchestrator-detail-wide"><h3>Worker Note</h3><p>Worker reassignment is simulated locally and does not call backend execution paths.</p></div>
            </div>
          ) : null}
          {activeTab === "Retry History" ? (
            <div className="workflow-orchestrator-retry-list">
              {(workflow.retry_history.length ? workflow.retry_history : [{ label: "No retry events recorded", count: 0, timestamp: "", detail: "Retry pressure is derived from available endpoint data." }]).map((item, index) => (
                <div key={`${item.label}-${index}`}>
                  <Repeat2 size={15} />
                  <b>{item.label}</b>
                  <span>{item.count} retry</span>
                  <small>{formatDateTime(item.timestamp)}{item.detail ? ` - ${item.detail}` : ""}</small>
                </div>
              ))}
            </div>
          ) : null}
          {activeTab === "Escalations" ? (
            <div className="workflow-orchestrator-detail-grid">
              <div className="workflow-orchestrator-detail-card"><span>Required</span><b>{workflow.escalation_required ? "Yes" : "No"}</b></div>
              <div className="workflow-orchestrator-detail-card"><span>Recommended</span><b>{workflow.recommended_action}</b></div>
              <div className="workflow-orchestrator-detail-wide"><h3>Escalation Basis</h3><p>{workflow.escalation_required ? [...workflow.blockers, ...workflow.risks].join(" | ") || "Manual review required." : "No escalation requirement detected."}</p></div>
            </div>
          ) : null}
          {activeTab === "Audit" ? <RiskList items={workflow.audit} empty="No audit entries detected." /> : null}
          <p className="workflow-orchestrator-safety-note">Simulation Mode Only — No Real Submission Execution. No backend mutation, portal upload, email send, CAPTCHA bypass, or final submit action is available here.</p>
        </div>
      </aside>
    </div>
  );
}

export default function WorkflowOrchestratorWorkspace() {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], error: "" });
  const [workflows, setWorkflows] = useState([]);
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [stage, setStage] = useState("All");
  const [retryPressure, setRetryPressure] = useState("All");
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [escalationOnly, setEscalationOnly] = useState(false);
  const [highProfitOnly, setHighProfitOnly] = useState(false);
  const [readyOnly, setReadyOnly] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Lifecycle");
  const [operatorState, setOperatorState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadWorkflows() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(WORKFLOW_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeWorkflowRecord(record, record._sourcePath));

      const merged = mergeWorkflows(records).filter((workflow) => workflow.rfq_id !== "RFQ" || workflow.buyer !== "Unknown Buyer");
      setWorkflows(merged.length ? merged : DEMO_WORKFLOWS);
      setEndpointState({
        loading: false,
        results,
        error: results.some((result) => result.ok) ? "" : "No orchestration endpoints responded with usable data.",
      });
    }

    loadWorkflows();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedWorkflow = useMemo(() => workflows.find((workflow) => workflow.rfq_id === selectedId), [selectedId, workflows]);
  const stageCounts = useMemo(() => {
    const base = Object.fromEntries(STAGES.map((item) => [item, 0]));
    workflows.forEach((workflow) => {
      base[workflow.current_stage] = (base[workflow.current_stage] || 0) + 1;
    });
    return base;
  }, [workflows]);

  const filteredWorkflows = useMemo(() => {
    const term = query.trim().toLowerCase();
    return workflows.filter((workflow) => {
      const haystack = `${workflow.rfq_id} ${workflow.title} ${workflow.buyer} ${workflow.current_stage} ${workflow.worker_assignment}`.toLowerCase();
      const ready = workflow.readiness_score >= 80 && !workflow.blockers.length && workflow.current_stage !== "blocked";
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || workflow.province === province) &&
        (stage === "All" || workflow.current_stage === stage) &&
        (retryPressure === "All" || workflow.retry_pressure === retryPressure) &&
        (!blockedOnly || workflow.blockers.length > 0 || workflow.current_stage === "blocked") &&
        (!escalationOnly || workflow.escalation_required) &&
        (!highProfitOnly || workflow.estimated_profit >= HIGH_PROFIT_THRESHOLD) &&
        (!readyOnly || ready)
      );
    });
  }, [blockedOnly, escalationOnly, highProfitOnly, province, query, readyOnly, retryPressure, stage, workflows]);

  const summary = useMemo(() => ({
    total: workflows.length,
    ready: workflows.filter((workflow) => workflow.readiness_score >= 80 && !workflow.blockers.length).length,
    escalated: workflows.filter((workflow) => workflow.escalation_required).length,
    blocked: workflows.filter((workflow) => workflow.blockers.length > 0 || workflow.current_stage === "blocked").length,
    profit: workflows.reduce((sum, workflow) => sum + Number(workflow.estimated_profit || 0), 0),
  }), [workflows]);

  const focusedWorkflow = selectedWorkflow || filteredWorkflows[0] || workflows[0] || DEMO_WORKFLOWS[0];
  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = workflows.some((workflow) => workflow._demo);
  const retryPressureRows = filteredWorkflows.slice(0, 10);
  const escalationQueue = filteredWorkflows.filter((workflow) => workflow.escalation_required);
  const throughputValues = STAGES.map((item) => stageCounts[item] || 0);
  const averageReadiness = workflows.length ? Math.round(workflows.reduce((sum, workflow) => sum + workflow.readiness_score, 0) / workflows.length) : 0;

  function openWorkflow(workflow) {
    setSelectedId(workflow.rfq_id);
    setActiveTab("Lifecycle");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  return (
    <section className="workflow-orchestrator-workspace" id="workflow-orchestrator-workspace">
      <div className="workflow-orchestrator-simulation-banner card">
        <div>
          <p className="eyebrow">Autonomous Workflow Orchestrator</p>
          <h2>Simulation Mode Only — No Real Submission Execution</h2>
          <p className="muted">Read-only orchestration monitor probing {API_BASE}. Operator controls are local simulation state only.</p>
        </div>
        <div className="workflow-orchestrator-safety-locks">
          {["no_backend_mutation", "no_portal_upload", "no_email_send", "no_captcha_bypass", "no_final_submit"].map((lock) => (
            <span key={lock}><ShieldAlert size={14} />{lock}</span>
          ))}
        </div>
      </div>

      <div className="workflow-orchestrator-hero card">
        <div>
          <p className="eyebrow">Workflow Orchestrator</p>
          <h1>Autonomous Workflow Orchestrator Workspace</h1>
          <p className="muted">Lifecycle visibility, readiness scoring, worker assignment, retry pressure, and escalation tracking.</p>
        </div>
        <div className="workflow-orchestrator-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${WORKFLOW_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="workflow-orchestrator-summary-grid">
        <div className="workflow-orchestrator-summary-card"><span>Workflow Items</span><b>{summary.total}</b></div>
        <div className="workflow-orchestrator-summary-card good"><span>Ready</span><b>{summary.ready}</b></div>
        <div className="workflow-orchestrator-summary-card amber"><span>Escalations</span><b>{summary.escalated}</b></div>
        <div className="workflow-orchestrator-summary-card bad"><span>Blocked</span><b>{summary.blocked}</b></div>
        <div className="workflow-orchestrator-summary-card blue"><span>Est. Profit</span><b>{money(summary.profit)}</b></div>
      </div>

      <div className="workflow-orchestrator-toolbar card">
        <label className="workflow-orchestrator-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search RFQ, buyer, worker, stage" /></label>
        <label><Filter size={15} /><select value={province} onChange={(event) => setProvince(event.target.value)}>{PROVINCES.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={stage} onChange={(event) => setStage(event.target.value)}>{["All", ...STAGES].map((item) => <option key={item} value={item}>{stageLabel(item)}</option>)}</select></label>
        <label><Filter size={15} /><select value={retryPressure} onChange={(event) => setRetryPressure(event.target.value)}>{["All", "Low", "Medium", "High"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <button className={blockedOnly ? "active" : ""} type="button" onClick={() => setBlockedOnly((value) => !value)}><ShieldAlert size={15} />Blocked only</button>
        <button className={escalationOnly ? "active" : ""} type="button" onClick={() => setEscalationOnly((value) => !value)}><AlertTriangle size={15} />Escalations</button>
        <button className={highProfitOnly ? "active" : ""} type="button" onClick={() => setHighProfitOnly((value) => !value)}><TrendingUp size={15} />High profit</button>
        <button className={readyOnly ? "active" : ""} type="button" onClick={() => setReadyOnly((value) => !value)}><CheckCircle2 size={15} />Ready</button>
      </div>

      {endpointState.error ? <div className="workflow-orchestrator-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="workflow-orchestrator-warning"><GitBranch size={16} />No live orchestration rows were found. Showing a non-destructive simulation preview row.</div> : null}

      <div className="workflow-orchestrator-pipeline card">
        <div className="card-head">
          <h2>Workflow Pipeline Map</h2>
          <span>{filteredWorkflows.length} filtered</span>
        </div>
        <div className="workflow-orchestrator-stage-flow">
          {STAGES.map((item, index) => (
            <div className={`workflow-orchestrator-stage-card stage-${item}`} key={item}>
              <StageChip stage={item} />
              <b>{stageCounts[item] || 0}</b>
              <small>{index < STAGES.length - 1 ? "flow gate" : "terminal"}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="workflow-orchestrator-main-grid">
        <div className="workflow-orchestrator-table-card card">
          <div className="card-head">
            <h2>Stage Transition Queue</h2>
            <span>{filteredWorkflows.length} visible</span>
          </div>
          <div className="workflow-orchestrator-table-scroll">
            <table className="workflow-orchestrator-table">
              <thead>
                <tr>
                  <th>RFQ</th>
                  <th>Buyer</th>
                  <th>Stage</th>
                  <th>Next</th>
                  <th>Readiness</th>
                  <th>Worker</th>
                  <th>Retry</th>
                  <th>Proof</th>
                  <th>Profit</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredWorkflows.map((workflow, index) => (
                  <tr key={`${workflow.rfq_id}-${index}`} onClick={() => openWorkflow(workflow)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openWorkflow(workflow)}>
                    <td><b>{workflow.rfq_id}</b><span>{workflow.title}</span></td>
                    <td>{workflow.buyer}<small>{workflow.province}</small></td>
                    <td><StageChip stage={workflow.current_stage} /></td>
                    <td><StageChip stage={workflow.next_stage} /></td>
                    <td><StatusChip label="Ready" status={`${workflow.readiness_score}`} tone={scoreTone(workflow.readiness_score)} /></td>
                    <td>{workflow.worker_assignment}</td>
                    <td><StatusChip label="Retry" status={workflow.retry_pressure} tone={retryTone(workflow.retry_pressure)} /></td>
                    <td><StatusChip label="Proof" status={workflow.proof_status} /></td>
                    <td>{money(workflow.estimated_profit)}</td>
                    <td><button className="workflow-orchestrator-row-button" type="button" onClick={(event) => { event.stopPropagation(); openWorkflow(workflow); }}>Open</button></td>
                  </tr>
                ))}
                {!filteredWorkflows.length ? (
                  <tr><td colSpan="10"><div className="workflow-orchestrator-empty-inline">No workflow items match the current filters.</div></td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <PanelShell title="Autonomous Readiness Monitor" icon={Gauge}>
          <div className="workflow-orchestrator-gauge-grid">
            <ReadinessGauge score={averageReadiness} label="average" />
            <ReadinessGauge score={focusedWorkflow.readiness_score} label="focused" />
          </div>
          <div className="workflow-orchestrator-monitor-note">
            <b>{focusedWorkflow.rfq_id}</b>
            <span>{focusedWorkflow.recommended_action}</span>
          </div>
        </PanelShell>
      </div>

      <div className="workflow-orchestrator-panels">
        <PanelShell title="Worker Assignment Panel" icon={Cpu}>
          <div className="workflow-orchestrator-worker-list">
            {filteredWorkflows.slice(0, 8).map((workflow, index) => (
              <button type="button" key={`${workflow.rfq_id}-worker-${index}`} onClick={() => openWorkflow(workflow)}>
                <Cpu size={15} />
                <div><b>{workflow.worker_assignment}</b><span>{workflow.rfq_id} - {stageLabel(workflow.current_stage)}</span></div>
              </button>
            ))}
          </div>
        </PanelShell>

        <PanelShell title="Retry / Failure Pressure" icon={Repeat2}>
          <div className="workflow-orchestrator-heat-list">
            {retryPressureRows.map((workflow, index) => <HeatBar key={`${workflow.rfq_id}-retry-${index}`} value={workflow.retry_pressure} label={workflow.rfq_id} />)}
            {!retryPressureRows.length ? <div className="workflow-orchestrator-empty-inline">No retry pressure rows available.</div> : null}
          </div>
        </PanelShell>

        <PanelShell title="Escalation Queue" icon={ShieldAlert}>
          <div className="workflow-orchestrator-escalation-list">
            {escalationQueue.slice(0, 8).map((workflow, index) => (
              <button type="button" key={`${workflow.rfq_id}-esc-${index}`} onClick={() => openWorkflow(workflow)}>
                <StatusChip label="Escalation" status={workflow.escalation_required ? "Required" : "Clear"} tone={workflow.escalation_required ? "amber" : "green"} />
                <div><b>{workflow.rfq_id}</b><span>{workflow.recommended_action}</span></div>
              </button>
            ))}
            {!escalationQueue.length ? <div className="workflow-orchestrator-empty-inline">No escalation queue items.</div> : null}
          </div>
        </PanelShell>

        <PanelShell title="Lifecycle Timeline" icon={History}>
          <TimelineList timeline={focusedWorkflow.timeline} />
        </PanelShell>

        <PanelShell title="Orchestration Health" icon={Activity}>
          <div className="workflow-orchestrator-health-grid">
            <div><span>Endpoints</span><b>{liveCount}/{WORKFLOW_ENDPOINTS.length}</b></div>
            <div><span>Status</span><b>{endpointState.loading ? "Loading" : usingDemo ? "Fallback" : "Live"}</b></div>
            <div><span>Blocked</span><b>{summary.blocked}</b></div>
            <div><span>Mode</span><b>Simulation</b></div>
          </div>
        </PanelShell>

        <PanelShell title="Throughput Metrics" icon={BarChart3}>
          <div className="workflow-orchestrator-throughput">
            <TrendLine values={throughputValues} />
            <div>
              <span>Stage flow count</span>
              <b>{throughputValues.reduce((sum, value) => sum + value, 0)}</b>
              <small>{STAGES.map((item) => `${stageLabel(item)} ${stageCounts[item] || 0}`).join(" | ")}</small>
            </div>
          </div>
        </PanelShell>
      </div>

      <DetailDrawer
        workflow={selectedWorkflow}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
      />
    </section>
  );
}
