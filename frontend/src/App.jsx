import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  BrainCircuit,
  Calculator,
  ClipboardList,
  Cpu,
  LayoutDashboard,
  ListChecks,
  PackageCheck,
  RefreshCw,
  ScrollText,
  Send,
  Settings,
  ShieldCheck,
} from "lucide-react";
import {
  API_BASE,
  getAutonomousStatus,
  getDashboardSummary,
  getHealth,
  getOpportunities,
  getPortalHealth,
  getRadarStatus,
  getQuoteCompilationComplianceSummary,
  getQuoteCompilationLatestPack,
  getQuoteCompilationPacks,
  getSubmissionHistory,
  getSubmissionProfit,
  getSubmissionSummary,
  getPolicy,
  getRfqLifecycleMissionControl,
  getRfqLifecycleAnalytics,
  getRfqLifecycleTelemetry,
  updatePolicy,
  runAutonomousOnce,
} from "./services/api";
import "./App.css";
import LiveSubmissionFeedPanel from "./components/LiveSubmissionFeedPanel";
import PortalWorkersWorkspace from "./components/PortalWorkersWorkspace";
import ProofAuditCentreWorkspace from "./components/ProofAuditCentreWorkspace";
import QuotePackEngineWorkspace from "./components/QuotePackEngineWorkspace";
import RfqOperationsWorkspace from "./components/RfqOperationsWorkspace";
import SubmissionCentreWorkspace from "./components/SubmissionCentreWorkspace";
import WebSocketAutoConnector from "./components/WebSocketAutoConnector";
import WorkflowOrchestratorWorkspace from "./components/WorkflowOrchestratorWorkspace";

const REFRESH_MS = 15000;
const provinces = ["GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP"];
const navItems = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, workspace: "dashboard" },
  { key: "rfq-operations", label: "RFQ Operations", icon: ClipboardList, workspace: "rfq-operations" },
  { key: "workflow-orchestrator", label: "Workflow Orchestrator", icon: Activity, workspace: "workflow-orchestrator" },
  { key: "rfq-intelligence", label: "RFQ Intelligence", icon: BrainCircuit, targetId: "rfq-intelligence" },
  { key: "harvest-queue", label: "Harvest Queue", icon: ListChecks, targetId: "harvest-queue" },
  { key: "quote-pack-engine", label: "Quote Pack Engine", icon: PackageCheck, workspace: "quote-pack-engine" },
  { key: "quote-engine", label: "Quote Engine", icon: Calculator, targetId: "quote-engine" },
  { key: "submission-centre", label: "Submission Centre", icon: Send, workspace: "submission-centre" },
  { key: "proof-audit-centre", label: "Proof & Audit Centre", icon: ScrollText, workspace: "proof-audit-centre" },
  { key: "proof-centre", label: "Proof Centre", icon: ShieldCheck, targetId: "submission-centre" },
  { key: "portal-health", label: "Portal Health", icon: Activity, targetId: "portal-health" },
  { key: "portal-workers", label: "Portal Workers", icon: Cpu, workspace: "portal-workers" },
  { key: "workers", label: "Workers", icon: Cpu, targetId: "rfq-intelligence" },
  { key: "compliance", label: "Compliance", icon: BadgeCheck, targetId: "rfq-intelligence" },
  { key: "audit-trail", label: "Audit Trail", icon: ScrollText, targetId: "submission-centre" },
  { key: "settings", label: "Settings", icon: Settings },
];

function money(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(n);
}

function compact(value) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}m`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

function readCount(obj, keys, fallback = 0) {
  for (const key of keys) {
    if (obj && obj[key] !== undefined && obj[key] !== null) return obj[key];
  }
  return fallback;
}

function stageOf(item) {
  const status = String(item.submission_status || item.pipeline_status || item.status || "new").toLowerCase();
  if (status.includes("submitted")) return "Submitted";
  if (status.includes("pack") || status.includes("pdf") || status.includes("quote")) return "Quote Pack";
  if (status.includes("eligible") || status.includes("ready")) return "Ready";
  if (status.includes("reject") || status.includes("skip") || status.includes("fail")) return "Blocked";
  return "Harvested";
}

function provinceOf(item) {
  const raw = String(item.province || item.buyer_province || item.location || item.region || "").toUpperCase();
  if (raw.includes("GAUTENG") || raw === "GP") return "GP";
  if (raw.includes("FREE STATE") || raw === "FS") return "FS";
  if (raw.includes("KWAZULU") || raw.includes("KZN")) return "KZN";
  if (raw.includes("WESTERN CAPE") || raw === "WC") return "WC";
  if (raw.includes("EASTERN CAPE") || raw === "EC") return "EC";
  if (raw.includes("NORTHERN CAPE") || raw === "NC") return "NC";
  if (raw.includes("NORTH WEST") || raw === "NW") return "NW";
  if (raw.includes("MPUMALANGA") || raw === "MP") return "MP";
  if (raw.includes("LIMPOPO") || raw === "LP") return "LP";
  return "FS";
}

function MiniBars({ data = [] }) {
  const max = Math.max(1, ...data.map((d) => Number(d.value || 0)));
  return <div className="mini-bars">{data.map((d, i) => <span key={i} title={`${d.label}: ${d.value}`} style={{ height: `${18 + (Number(d.value || 0) / max) * 54}px` }} />)}</div>;
}

function Donut({ percent = 0, label }) {
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  return <div className="donut" style={{ background: `conic-gradient(#18e6a6 ${p}%, rgba(255,255,255,.12) 0)` }}><div><b>{Math.round(p)}%</b><small>{label}</small></div></div>;
}

function Stat({ label, value, tone = "" }) {
  return <div className={`stat ${tone}`}><span>{label}</span><b>{value}</b></div>;
}

function text(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  const result = String(value).trim();
  return result || fallback;
}

function SparkLine({ values = [] }) {
  const safe = values.length ? values : [1, 2, 1, 3, 2, 4, 3];
  const max = Math.max(...safe, 1);
  const points = safe.map((v, i) => `${(i / Math.max(1, safe.length - 1)) * 100},${36 - (v / max) * 30}`).join(" ");
  return <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><polyline points={points} /></svg>;
}

function ComplianceStatusPanel({
  packId,
  packOptions = [],
  inputPackId,
  onPackIdChange,
  onLoad,
  loading = false,
  summary = null,
  error = "",
}) {
  const summaryStatus = text(summary?.status, "unknown");
  const statusClass = summaryStatus === "ready_manual_only" ? "good" : summaryStatus === "blocked" ? "bad" : "gold";
  const manualCompletionLabel = summary ? (summary.manual_completion_present ? "Present" : "Missing") : "Not loaded";
  const proofCompletionLabel = summary ? text(summary?.submission_proof_status || (summary.submission_proof_present ? "ok" : "missing"), summary.submission_proof_present ? "present" : "missing") : "Not loaded";
  const readinessLabel = summary ? (summary.readiness_checklist_available ? "Available" : "Unavailable") : "Not loaded";
  const evidenceLabel = summary ? (summary.evidence_bundle_available ? "Available" : "Unavailable") : "Not loaded";
  const snapshotLabel = summary ? (summary.evidence_snapshot_available ? text(summary.evidence_snapshot_verification_status, "Available") : "Unavailable") : "Not loaded";
  const finalSubmitLabel = summary ? (summary.final_submit_locked ? "Locked" : "Open") : "Not loaded";
  const automatedLabel = summary ? (summary.automated_submit_disabled ? "Disabled" : "Enabled") : "Not loaded";
  const blockers = Array.isArray(summary?.blockers) ? summary.blockers.slice(0, 3) : [];
  const warnings = Array.isArray(summary?.warnings) ? summary.warnings.slice(0, 3) : [];
  const selectedPack = packOptions.find((pack) => pack.pack_id === inputPackId);
  const snapshotHash = summary?.evidence_snapshot_hash || "Not loaded";

  return (
    <section className="card dashboard-compliance-card" id="submission-compliance-status">
      <div className="dashboard-compliance-head">
        <div>
          <p className="eyebrow">Submission Compliance</p>
          <h2>Submission Compliance Status</h2>
          <p className="muted">Pack-local readiness summary without opening the Submission Centre.</p>
        </div>
        <span className={`ops-badge ${statusClass}`}>{summaryStatus.replaceAll("_", " ")}</span>
      </div>

      <div className="dashboard-compliance-controls">
        <label>
          <span>Pack ID</span>
          <input
            type="text"
            value={inputPackId}
            onChange={(event) => onPackIdChange(event.target.value)}
            placeholder="Enter or select a pack"
            spellCheck={false}
          />
        </label>
        <label>
          <span>Recent packs</span>
          <select value={inputPackId} onChange={(event) => onPackIdChange(event.target.value)}>
            <option value="">Select a pack</option>
            {packOptions.map((pack) => (
              <option key={pack.pack_id} value={pack.pack_id}>
                {pack.pack_id}{pack.rfq_reference ? ` · ${pack.rfq_reference}` : ""}{pack.title ? ` · ${pack.title}` : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => onLoad(inputPackId)} disabled={!inputPackId || loading}>
          <RefreshCw size={14} /> {loading ? "Loading" : "Load"}
        </button>
      </div>

      {error ? <div className="dashboard-compliance-warning"><AlertTriangle size={15} />{error}</div> : null}

      <div className="dashboard-compliance-grid">
        <div><span>Status</span><b>{summaryStatus.replaceAll("_", " ")}</b></div>
        <div><span>Manual Completion</span><b>{manualCompletionLabel}</b></div>
        <div><span>Submission Proof</span><b>{proofCompletionLabel}</b></div>
        <div><span>Readiness Checklist</span><b>{readinessLabel}</b></div>
        <div><span>Evidence Bundle</span><b>{evidenceLabel}</b></div>
        <div><span>Evidence Snapshot</span><b>{snapshotLabel}</b></div>
        <div><span>Audit Events</span><b>{summary ? compact(summary.audit_event_count) : "0"}</b></div>
        <div><span>Warnings</span><b>{summary ? compact(summary.audit_warning_count) : "0"}</b></div>
        <div><span>Final Submit</span><b>{finalSubmitLabel}</b></div>
        <div><span>Automated Submit</span><b>{automatedLabel}</b></div>
        <div><span>Pack</span><b>{summary?.pack_id || selectedPack?.pack_id || packId || "Unknown"}</b></div>
        <div><span>Snapshot Hash</span><b>{snapshotHash}</b></div>
      </div>

      <div className="dashboard-compliance-meta">
        <div><span>Generated</span><b>{summary?.generated_at || "Not loaded"}</b></div>
        <div><span>Submission Proof Saved</span><b>{summary?.submission_proof_saved_at || "Not loaded"}</b></div>
        <div><span>Snapshot Generated</span><b>{summary?.evidence_snapshot_generated_at || "Not loaded"}</b></div>
        <div><span>Latest audit</span><b>{summary?.latest_audit_event_summary || "None"}</b></div>
      </div>

      <div className="dashboard-compliance-columns">
        <div>
          <h3>Blockers</h3>
          {blockers.length ? blockers.map((item, index) => <p key={`blocker-${index}`}><b>{index + 1}</b>{text(item, "Blocked")}</p>) : <p><b>0</b>No blockers reported.</p>}
        </div>
        <div>
          <h3>Warnings</h3>
          {warnings.length ? warnings.map((item, index) => <p key={`warning-${index}`}><b>{index + 1}</b>{text(item, "Warning")}</p>) : <p><b>0</b>No warnings reported.</p>}
        </div>
      </div>
    </section>
  );
}

function MetricList({ rows = [], valueKey = "value", labelKey = "label", empty = "No data" }) {
  const visible = rows.slice(0, 5);
  return <div className="metric-list">{visible.length ? visible.map((row, i) => <div key={i}><span>{row[labelKey]}</span><b>{row[valueKey]}</b></div>) : <p>{empty}</p>}</div>;
}

function LifecyclePanel({ lifecycle = {}, analytics = {}, telemetry = {} }) {
  const queue = lifecycle.queue_by_lifecycle_state || {};
  const states = ["DISCOVERED", "QUALIFIED", "DOCUMENTS_PARSED", "PRICED", "QUOTE_PACK_READY", "SUBMISSION_READY", "FAILED", "REVIEW_REQUIRED"];
  const blockers = Array.isArray(lifecycle.blockers) ? lifecycle.blockers.slice(0, 3) : [];
  const safety = lifecycle.safety || {};
  const latencyRows = Object.entries(analytics.per_stage_latency || {}).map(([label, value]) => ({ label: label.replaceAll("_", " "), value: `${Number(value || 0).toFixed(2)}s` })).sort((a, b) => parseFloat(b.value) - parseFloat(a.value));
  const queueRows = Object.entries(analytics.queue_wait_times || {}).map(([label, value]) => ({ label: label.replace("_queue", ""), value: `${Number(value || 0).toFixed(1)}s` }));
  const retryRows = Object.entries(analytics.task_retry_histogram || {}).map(([label, value]) => ({ label: `${label} retries`, value }));
  const lifecycleSourceReliability = Array.isArray(lifecycle.source_reliability) ? lifecycle.source_reliability : [];
  const sourceRows = Array.isArray(analytics.source_reliability_score) && analytics.source_reliability_score.length
    ? analytics.source_reliability_score.map((row) => ({ label: row.source || "source", value: `${Number(row.reliability_score || 0).toFixed(0)}%` }))
    : lifecycleSourceReliability.map((row) => ({ label: row.source || "source", value: `${Number(row.reliability_score || 0).toFixed(0)}%` }));
  const acquisition = lifecycle.document_acquisition_throughput || {};
  const slowPortalRows = Array.isArray(lifecycle.slowest_portals) ? lifecycle.slowest_portals.map((row) => ({ label: row.source || "portal", value: `${Number(row.average_latency_seconds || 0).toFixed(2)}s` })) : [];
  const failedSourceRows = Array.isArray(lifecycle.failed_source_diagnostics?.dead_letter_by_source)
    ? lifecycle.failed_source_diagnostics.dead_letter_by_source.map((row) => ({ label: row.source || "source", value: row.count }))
    : [];
  const healthTrend = Array.isArray(analytics.system_health_trend) ? analytics.system_health_trend.map((row) => Number(row.health_score || 0)) : [];
  const queueTrend = Array.isArray(analytics.queue_trend) ? analytics.queue_trend.map((row) => Number(row.completed_rfqs || row.simulated_throughput || 0)) : [];
  const timeline = Array.isArray(analytics.rfq_lifecycle_timeline_samples) ? analytics.rfq_lifecycle_timeline_samples[0] : null;
  const timelineEvents = Array.isArray(timeline?.events) ? timeline.events.slice(-5) : [];
  const warnings = Array.isArray(analytics.worker_saturation_warnings) ? analytics.worker_saturation_warnings.slice(0, 3) : [];
  const infra = lifecycle.infrastructure_telemetry || telemetry || {};
  const broker = telemetry.broker_health || {};
  const backlog = telemetry.queue_backlog || infra.queue_backlog || {};
  const pressure = telemetry.resource_pressure || {};
  const stalled = Array.isArray(telemetry.stalled_lifecycle_tasks) ? telemetry.stalled_lifecycle_tasks : (infra.stalled_lifecycle_tasks || []);
  const restartEvents = Array.isArray(telemetry.worker_restart_events) ? telemetry.worker_restart_events : (infra.worker_restart_events || []);
  const infraWarnings = Array.isArray(telemetry.warnings) ? telemetry.warnings.slice(0, 3) : (infra.warnings || []);
  const distributed = telemetry.distributed_execution || infra.distributed_execution || {};
  const queueLoadRows = Object.entries(distributed.queue_specific_worker_load || {}).map(([label, row]) => ({ label: label.replace("_queue", ""), value: `${Number(row.concurrency_utilization || 0).toFixed(0)}% / ${Number(row.task_throughput || 0).toFixed(0)}` }));
  const activeWorkers = Array.isArray(distributed.active_workers) ? distributed.active_workers.length : (infra.worker_online_count || 0);
  return (
    <section className="lifecycle card" id="rfq-intelligence">
      <div className="card-head"><h2>RFQ Lifecycle Mission Control</h2><span>{lifecycle.status || "loading"}</span></div>
      <div className="lifecycle-grid">
        <Stat label="Total RFQs" value={compact(lifecycle.total_rfqs)} />
        <Stat label="Active" value={compact(lifecycle.active_rfqs)} tone="blue" />
        <Stat label="Failed" value={compact(lifecycle.failed_rfqs)} tone={lifecycle.failed_rfqs ? "bad" : "good"} />
        <Stat label="Review" value={compact(lifecycle.review_required_rfqs)} tone={lifecycle.review_required_rfqs ? "gold" : "good"} />
        <Stat label="Submitted" value={compact(lifecycle.submitted_rfqs)} />
        <Stat label="Proofs" value={compact(lifecycle.proof_captured_rfqs)} />
        <Stat label="Monthly Cap." value={compact(lifecycle.estimated_monthly_capacity)} tone="blue" />
        <Stat label="Final Submit" value={safety.final_submit_hard_blocked_by_lifecycle ? "LOCKED" : "CHECK"} tone={safety.final_submit_hard_blocked_by_lifecycle ? "good" : "bad"} />
      </div>
      <div className="lifecycle-state-grid">
        {states.map((name) => <div key={name} className={(name === "FAILED" && queue[name]) || (name === "REVIEW_REQUIRED" && queue[name]) ? "state-chip hot" : "state-chip"}><span>{name.replaceAll("_", " ")}</span><b>{queue[name] || 0}</b></div>)}
      </div>
      <div className="lifecycle-footer">
        <div><b>Next:</b> {lifecycle.next_recommended_action || "ingest next discovery batch"}</div>
        <div><b>Policy:</b> supply only · margin 25% · profit R30k · CAPTCHA bypass {safety.captcha_bypass_allowed ? "on" : "off"}</div>
        <div><b>Blockers:</b> {(blockers.length ? blockers : ["none"]).join(" | ")}</div>
      </div>
      <div className="observability-grid">
        <div className="obs-panel"><h3>Health Trend</h3><SparkLine values={healthTrend} /><small>score {compact(lifecycle.lifecycle_health_score)}</small></div>
        <div className="obs-panel"><h3>Queue Trend</h3><SparkLine values={queueTrend} /><small>pressure {lifecycle.queue_pressure || "idle"}</small></div>
        <div className="obs-panel"><h3>Retry Pressure</h3><MetricList rows={retryRows} /></div>
        <div className="obs-panel"><h3>Slowest Stages</h3><MetricList rows={latencyRows} /></div>
        <div className="obs-panel"><h3>Queue Wait</h3><MetricList rows={queueRows} /></div>
        <div className="obs-panel"><h3>Source Reliability</h3><MetricList rows={sourceRows} valueKey="value" labelKey="label" /></div>
        <div className="obs-panel"><h3>Acquisition</h3><MetricList rows={[
          { label: "resolution", value: `${Number(acquisition.document_resolution_rate || 0).toFixed(0)}%` },
          { label: "throughput", value: `${Number(acquisition.download_throughput_per_minute || 0).toFixed(0)}/min` },
          { label: "dead letters", value: compact(acquisition.dead_letter_count || 0) },
          { label: "direct fast path", value: compact(acquisition.direct_link_fast_path_total || 0) },
        ]} /></div>
        <div className="obs-panel"><h3>Slow Portals</h3><MetricList rows={slowPortalRows} /></div>
        <div className="obs-panel"><h3>Failed Sources</h3><MetricList rows={failedSourceRows} /></div>
        <div className="obs-panel"><h3>Queue Load</h3><MetricList rows={queueLoadRows} empty="No active workers" /></div>
        <div className="obs-panel timeline"><h3>RFQ Timeline</h3><b>{timeline?.rfq_id || "No RFQ selected"}</b>{timelineEvents.map((event, i) => <p key={i}><span>{event.to_state || event.state || event.event}</span>{event.reason || event.event}</p>)}</div>
      </div>
      <div className="infra-grid">
        <Stat label="Workers" value={compact(activeWorkers)} tone={(telemetry.worker_online ?? infra.worker_online) ? "good" : "bad"} />
        <Stat label="Broker" value={(broker.connected ?? infra.broker_connected) ? "OK" : "WARN"} tone={(broker.connected ?? infra.broker_connected) ? "good" : "bad"} />
        <Stat label="Backlog" value={compact(backlog.total_backlog)} tone={backlog.backlog_detected ? "gold" : "good"} />
        <Stat label="Stalled" value={compact(stalled.length)} tone={stalled.length ? "bad" : "good"} />
        <Stat label="Memory" value={pressure.memory_pressure_warning || infra.memory_pressure ? "HIGH" : "OK"} tone={pressure.memory_pressure_warning || infra.memory_pressure ? "bad" : "good"} />
        <Stat label="CPU" value={pressure.cpu_saturation_warning || infra.cpu_pressure ? "HIGH" : "OK"} tone={pressure.cpu_saturation_warning || infra.cpu_pressure ? "bad" : "good"} />
        <Stat label="Concurrency" value={`${Math.round(distributed.concurrency_utilization || 0)}%`} tone={(distributed.concurrency_utilization || 0) > 85 ? "gold" : ""} />
        <Stat label="Resilience" value={`${Math.round(telemetry.system_resilience_score ?? infra.system_resilience_score ?? 0)}%`} tone={(telemetry.system_resilience_score ?? infra.system_resilience_score ?? 0) >= 70 ? "good" : "bad"} />
      </div>
      <div className="infra-footer">
        <div><b>Telemetry:</b> {(infraWarnings.length ? infraWarnings : ["nominal"]).join(" | ")}</div>
        <div><b>Execution:</b> pool {distributed.worker_pool || "prefork"} · capacity {compact(distributed.total_concurrency_capacity)} · prefetch {distributed.prefetch_multiplier || 1}</div>
        <div><b>Restarts:</b> {compact(telemetry.worker_restart_count ?? infra.worker_restart_count)} · {restartEvents.length ? restartEvents.map((x) => x.worker || "worker").join(", ") : "none detected"}</div>
      </div>
    </section>
  );
}

export default function App() {
  const [state, setState] = useState({ loading: true, lastUpdated: null });
  const [busy, setBusy] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState("dashboard");
  const [complianceCatalog, setComplianceCatalog] = useState({ loading: true, items: [], error: "" });
  const [compliancePackId, setCompliancePackId] = useState("");
  const [complianceSummaryState, setComplianceSummaryState] = useState({ loading: false, data: null, error: "", loadedPackId: "" });

  async function loadComplianceSummary(packId) {
    const safePackId = String(packId || "").trim();
    if (!safePackId) {
      setComplianceSummaryState({ loading: false, data: null, error: "Select a pack ID to load a compliance summary.", loadedPackId: "" });
      return;
    }
    setComplianceSummaryState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await getQuoteCompilationComplianceSummary(safePackId);
    if (result?.status === "offline" && result?.error) {
      setComplianceSummaryState({ loading: false, data: null, error: result.error || "Compliance summary unavailable.", loadedPackId: safePackId });
      return;
    }
    setComplianceSummaryState({
      loading: false,
      data: result,
      error: "",
      loadedPackId: safePackId,
    });
  }

  useEffect(() => {
    let cancelled = false;

    async function loadComplianceCatalog() {
      const [packsResponse, latestResponse] = await Promise.all([
        getQuoteCompilationPacks(8),
        getQuoteCompilationLatestPack(),
      ]);
      if (cancelled) return;
      const items = Array.isArray(packsResponse?.items) ? packsResponse.items : [];
      const latestPackId = text(latestResponse?.pack_id || items[0]?.pack_id, "");
      setComplianceCatalog({
        loading: false,
        items,
        error: !items.length ? "No local quote packs were found." : "",
      });
      if (latestPackId) {
        setCompliancePackId((current) => current || latestPackId);
        await loadComplianceSummary(latestPackId);
      } else {
        setComplianceSummaryState({ loading: false, data: null, error: "", loadedPackId: "" });
      }
    }

    loadComplianceCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  async function load() {
    const [health, auto, summary, opps, subSummary, profit, history, portal, radar, policy, lifecycle, lifecycleAnalytics, lifecycleTelemetry] = await Promise.all([
      getHealth(), getAutonomousStatus(), getDashboardSummary(), getOpportunities(), getSubmissionSummary(), getSubmissionProfit(), getSubmissionHistory(), getPortalHealth(), getRadarStatus(), getPolicy(), getRfqLifecycleMissionControl(), getRfqLifecycleAnalytics(), getRfqLifecycleTelemetry(),
    ]);
    setState({ health, auto, summary, opps, subSummary, profit, history, portal, radar, policy, lifecycle, lifecycleAnalytics, lifecycleTelemetry, loading: false, lastUpdated: new Date() });
  }

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const opps = state.opps || [];
  const history = state.history || [];
  const lifecycle = state.lifecycle || {};
  const telemetry = state.lifecycleTelemetry || {};
  const radarPayload = state.radar?.radar || state.radar || {};
  const queueByState = lifecycle.queue_by_lifecycle_state || {};

  const control = lifecycle?.safety?.system_control || {};
  const effectiveStatus = String(control.effective_system_status || state.policy?.policy?.mode || "controlled").toLowerCase();
  const systemOn = Boolean(
    control.system_on !== undefined
      ? control.system_on
      : effectiveStatus === "on" || effectiveStatus === "controlled"
        ? true
        : state.policy?.policy?.enabled ?? state.auto?.enabled ?? true
  );

  const submitted =
    readCount(lifecycle, ["proof_captured_rfqs", "proof_archive_count"], 0) ||
    readCount(radarPayload, ["proof_captured"], 0) ||
    readCount(state.subSummary, ["submitted", "total_submitted", "submitted_count"], 0);

  const harvested =
    readCount(lifecycle, ["total_rfqs"], 0) ||
    readCount(state.summary, ["harvested", "total_harvested", "opportunities"], opps.length);

  const quoteReady =
    readCount(queueByState, ["QUOTE_PACK_READY"], 0) ||
    readCount(queueByState, ["SUBMISSION_READY"], 0) ||
    opps.filter((x) => x.quote_ready || stageOf(x) === "Ready" || stageOf(x) === "Quote Pack").length;

  const blocked =
    readCount(lifecycle, ["failed_rfqs", "review_required_rfqs", "review_required_count"], 0) ||
    readCount(queueByState, ["FAILED"], 0) ||
    readCount(queueByState, ["REVIEW_REQUIRED"], 0) ||
    opps.filter((x) => stageOf(x) === "Blocked").length;

  const profitTotal =
    readCount(state.profit, ["total_profit", "profit", "estimated_profit"], 0) ||
    history.reduce((s, x) => s + Number(x.total_profit || x.profit || 0), 0);

  const backendStatus =
    state.health?.status === "healthy" || telemetry.worker_online || radarPayload.worker_online
      ? "healthy"
      : state.health?.status || "unknown";

  const displayMode =
    lifecycle?.safety?.system_control?.effective_system_status ||
    state.policy?.policy?.mode ||
    (systemOn ? "controlled" : "off");

  const stageCounts = useMemo(() => {
    const queue = lifecycle.queue_by_lifecycle_state || {};
    const liveCounts = {
      Harvested:
        Number(queue.DISCOVERED || 0) +
        Number(queue.QUALIFIED || 0) +
        Number(queue.DOCUMENTS_ACQUIRED || 0) +
        Number(queue.DOCUMENTS_PARSED || 0) +
        Number(queue.PRICED || 0),
      Ready:
        Number(queue.SUBMISSION_READY || 0),
      "Quote Pack":
        Number(queue.QUOTE_PACK_READY || 0),
      Submitted:
        Number(lifecycle.proof_captured_rfqs || lifecycle.proof_archive_count || 0),
      Blocked:
        Number(queue.FAILED || 0) +
        Number(queue.REVIEW_REQUIRED || 0) +
        Number(queue.READY_FOR_RETRY || 0) +
        Number(queue.REJECTED || 0),
    };

    const hasLiveCounts = Object.values(liveCounts).some((value) => Number(value || 0) > 0);
    if (hasLiveCounts) return liveCounts;

    const base = { Harvested: 0, Ready: 0, "Quote Pack": 0, Submitted: 0, Blocked: 0 };
    opps.forEach((x) => { base[stageOf(x)] = (base[stageOf(x)] || 0) + 1; });
    history.forEach((x) => { if (stageOf(x) === "Submitted") base.Submitted += 1; });
    return base;
  }, [opps, history, lifecycle]);

  const provinceCounts = useMemo(() => {
    const base = Object.fromEntries(provinces.map((p) => [p, 0]));
    opps.forEach((x) => { base[provinceOf(x)] += 1; });
    return base;
  }, [opps]);

  const trend = [
    { label: "D", value: readCount(state.subSummary, ["today", "daily", "submitted_today"], Math.min(submitted, 4)) },
    { label: "W", value: readCount(state.subSummary, ["week", "weekly", "submitted_this_week"], Math.min(submitted, 14)) },
    { label: "M", value: readCount(state.subSummary, ["month", "monthly", "submitted_this_month"], submitted) },
  ];

  async function toggleSystem() {
    setBusy(true);
    const currentPolicy = state.policy?.policy || { enabled: systemOn, mode: "controlled", allow_email_send: false, allow_portal_upload: true, allow_portal_final_submit: true };
    await updatePolicy({ ...currentPolicy, enabled: !systemOn });
    await load();
    setBusy(false);
  }

  async function runNow() {
    setBusy(true);
    await runAutonomousOnce();
    await load();
    setBusy(false);
  }

  function selectWorkspace(item) {
    if (item.workspace) {
      setActiveWorkspace(item.workspace);
      return;
    }
    setActiveWorkspace("dashboard");
    if (item.targetId) {
      requestAnimationFrame(() => {
        document.getElementById(item.targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  const topOpps = opps.slice(0, 9);
  const portalList = Array.isArray(state.portal?.portals) ? state.portal.portals.slice(0, 8) : [];
  const alerts = [
    backendStatus !== "healthy" && `Backend health: ${backendStatus || "unknown"}`,
    !systemOn && "Autonomous engine is OFF",
    blocked > 0 && `${blocked} tender(s) blocked or failed`,
    false && portalList.length === 0 && "Portal health endpoint not yet available",
  ].filter(Boolean);

  return (
    <div className="command-centre-layout">
      <aside className="command-sidebar" aria-label="Command centre navigation">
        <div className="sidebar-brand">
          <span>LMCP</span>
          <b>Command Centre</b>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.workspace ? activeWorkspace === item.workspace : false;
            return (
              <button key={item.key} className={active ? "active" : ""} type="button" aria-current={active ? "page" : undefined} onClick={() => selectWorkspace(item)}>
                <Icon size={17} strokeWidth={2.2} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-status">
          <span>Backend</span>
          <b>{backendStatus}</b>
        </div>
      </aside>

      <main className="dashboard-shell dashboard-view">
        <WebSocketAutoConnector />
        {activeWorkspace === "workflow-orchestrator" ? (
          <WorkflowOrchestratorWorkspace />
        ) : activeWorkspace === "portal-workers" ? (
          <PortalWorkersWorkspace />
        ) : activeWorkspace === "proof-audit-centre" ? (
          <ProofAuditCentreWorkspace />
        ) : activeWorkspace === "submission-centre" ? (
          <SubmissionCentreWorkspace />
        ) : activeWorkspace === "quote-pack-engine" ? (
          <QuotePackEngineWorkspace />
        ) : activeWorkspace === "rfq-operations" ? (
          <RfqOperationsWorkspace />
        ) : (
        <>
        <section className="hero card" id="dashboard">
        <div>
          <p className="eyebrow">LMCP AutoQuote Command Centre</p>
          <h1>Autonomous Tender Control Tower</h1>
          <p className="muted">Live backend: {API_BASE} · Refresh every {REFRESH_MS / 1000}s · {state.lastUpdated ? state.lastUpdated.toLocaleTimeString() : "loading"}</p>
        </div>
        <div className="hero-actions">
          <button className={`power ${systemOn ? "on" : "off"}`} onClick={toggleSystem} disabled={busy}>{busy ? "SYNC" : systemOn ? "SYSTEM ON" : "SYSTEM OFF"}</button>
          <button className="run" onClick={runNow} disabled={busy}>Run Now</button>
        </div>
      </section>

      <section className="kpi-grid">
        <Stat label="Harvested" value={compact(harvested)} />
        <Stat label="Quote Ready" value={compact(quoteReady)} tone="good" />
        <Stat label="Submitted" value={compact(submitted)} tone="blue" />
        <Stat label="Est. Profit" value={money(profitTotal)} tone="gold" />
        <Stat label="Backend" value={backendStatus} tone={backendStatus === "healthy" ? "good" : "bad"} />
        <Stat label="Mode" value={displayMode} />
      </section>

      <ComplianceStatusPanel
        packId={complianceSummaryState.loadedPackId || compliancePackId}
        packOptions={complianceCatalog.items}
        inputPackId={compliancePackId}
        onPackIdChange={setCompliancePackId}
        onLoad={loadComplianceSummary}
        loading={complianceCatalog.loading || complianceSummaryState.loading}
        summary={complianceSummaryState.data}
        error={complianceCatalog.error || complianceSummaryState.error}
      />

      <section className="main-grid">
        <div className="card radar">
          <div className="card-head"><h2>Radar</h2><span>{state.radar?.service_version || state.radar?.status || "active"}</span></div>
          <div className="radar-scope"><i /><i /><i /><b /></div>
          <div className="radar-stats"><Stat label="Sources" value={compact(readCount(state.summary, ["sources", "enabled_sources", "total_sources"], 1325))} /><Stat label="Eligible" value={compact(readCount(state.summary, ["eligible", "eligible_count"], quoteReady))} /></div>
        </div>

        <div className="card heatmap">
          <div className="card-head"><h2>South Africa Heatmap</h2><span>Province opportunity density</span></div>
          <div className="province-grid">{provinces.map((p) => <div className="province" key={p}><b>{p}</b><span>{provinceCounts[p]}</span><em style={{ opacity: Math.min(.95, .25 + provinceCounts[p] / Math.max(1, harvested)) }} /></div>)}</div>
        </div>

        <div className="card trends">
          <div className="card-head"><h2>Daily / Weekly / Monthly</h2><span>Submission trend</span></div>
          <MiniBars data={trend} />
          <div className="trend-labels">{trend.map((x) => <span key={x.label}>{x.label}: {x.value}</span>)}</div>
          <SparkLine values={trend.map((x) => Number(x.value || 0))} />
        </div>

        <div className="card donuts">
          <div className="card-head"><h2>Submission Readiness</h2><span>Live ratios</span></div>
          <div className="donut-row"><Donut percent={harvested ? (quoteReady / harvested) * 100 : 0} label="Ready" /><Donut percent={harvested ? (submitted / Math.max(1, harvested)) * 100 : 0} label="Submitted" /></div>
        </div>
      </section>

      <section className="lanes card" id="quote-engine">
        <div className="card-head"><h2>Tender Lanes</h2><span>Harvest → Ready → Pack → Submit</span></div>
        <div className="lane-grid">{Object.entries(stageCounts).map(([name, count]) => <div className="lane" key={name}><strong>{name}</strong><b>{count}</b><small>{name === "Submitted" ? "delivered" : name === "Blocked" ? "needs review" : "processing"}</small></div>)}</div>
      </section>

      <LifecyclePanel lifecycle={state.lifecycle} analytics={state.lifecycleAnalytics} telemetry={state.lifecycleTelemetry} />

      <section className="operations-stack">
        <div className="bottom-grid">
        <div className="card table-card" id="harvest-queue">
          <div className="card-head"><h2>Live Tender Stream</h2><span>{topOpps.length} visible</span></div>
          <div className="table-scroll"><table><thead><tr><th>RFQ</th><th>Buyer</th><th>Province</th><th>Stage</th><th>Profit</th></tr></thead><tbody>{topOpps.map((x, i) => <tr key={i}><td>{x.buyer_rfq_number || x.rfq_number || x.reference || "RFQ"}</td><td>{x.buyer_name || x.organisation || x.department || "Buyer"}</td><td>{provinceOf(x)}</td><td><span className="pill">{stageOf(x)}</span></td><td>{money(x.total_profit || x.estimated_profit || 0)}</td></tr>)}</tbody></table></div>
        </div>

        <div className="card portal-card" id="portal-health">
          <div className="card-head"><h2>Portal Health</h2><span>{portalList.length ? "live" : "fallback"}</span></div>
          <div className="portal-list">{(portalList.length ? portalList : [{ name: "eTenders", status: "monitored" }, { name: "SOE portals", status: "monitored" }, { name: "Municipal portals", status: "monitored" }, { name: "Provincial portals", status: "monitored" }]).map((p, i) => <div key={i}><b>{p.name || p.source || `Portal ${i + 1}`}</b><span>{p.status || p.health || "unknown"}</span></div>)}</div>
        </div>

        <div className="card alerts-card">
          <div className="card-head"><h2>Alerts</h2><span>{alerts.length || 0}</span></div>
          <div className="alerts">{(alerts.length ? alerts : ["No critical alerts detected"]).map((a, i) => <p key={i}>{a}</p>)}</div>
        </div>
        </div>
        <LiveSubmissionFeedPanel refreshMs={10000} />
      </section>
        </>
        )}
      </main>
    </div>
  );
}
