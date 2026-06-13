import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import MissionControlAiScoringPanel from "../mission-control/components/MissionControlAiScoringPanel.jsx";
import MissionControlQuoteIntelligencePanel from "../mission-control/components/MissionControlQuoteIntelligencePanel.jsx";
import BusinessIntelligenceExpansionPackPanel from "../mission-control/components/BusinessIntelligenceExpansionPackPanel.jsx";
import LiveSubmissionFeedPanel from "../mission-control/components/LiveSubmissionFeedPanel.jsx";
import "../mission-control/mission-control.css";
import "../mission-control/mission-control-health.css";
import "../mission-control/mission-control-trends.css";
import "../mission-control/mission-control-quote-intelligence.css";
import { fetchMissionControlSnapshot } from "../mission-control/services/missionControlSnapshot.js";
import { API_BASE, runAutonomousOnce, updatePolicy } from "../mission-control/services/missionControlApi.js";

const REFRESH_MS = 15000;
const provinces = ["GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP"];
const quickActions = [
  {
    label: "Open Review Queue",
    description: "Operator queue, approvals and manual review.",
    to: "/review",
  },
  {
    label: "Open RFQ Operations",
    description: "Harvest, qualification and operational flow.",
    to: "/operations",
  },
  {
    label: "Submission Readiness",
    description: "Review-ready status and blockers.",
    to: "/review",
  },
  {
    label: "Quote Intelligence",
    description: "Supplier quote pipeline and pricing signals.",
    to: "/supplier-quote-intelligence",
  },
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

function formatDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1000) return `${Math.round(n)}ms`;
  return `${(n / 1000).toFixed(1)}s`;
}

function formatAge(from, to = new Date()) {
  const start = from ? new Date(from) : null;
  if (!start || Number.isNaN(start.getTime())) return "—";
  const diff = Math.max(0, to.getTime() - start.getTime());
  if (diff < 1000) return "just now";
  if (diff < 60 * 1000) return `${Math.round(diff / 1000)}s ago`;
  if (diff < 60 * 60 * 1000) return `${Math.round(diff / 60000)}m ago`;
  return `${(diff / 3600000).toFixed(1)}h ago`;
}

function freshnessLabel(ageMs) {
  const n = Number(ageMs);
  if (!Number.isFinite(n)) return "unknown";
  if (n < 60000) return "fresh";
  if (n < 300000) return "warm";
  return "stale";
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

function SnapshotHealthPanel({ snapshot, lastUpdated, loadDurationMs, backendStatus, systemOn }) {
  const snapshotGeneratedAt = snapshot?.generatedAt || snapshot?.radar?.generatedAt || snapshot?.radar?.generated_at || null;
  const backendDependencyStatus = String(snapshot?.health?.status || snapshot?.radar?.backendStatus || backendStatus || "unknown");
  const snapshotAgeSource = snapshotGeneratedAt || lastUpdated;
  const snapshotAgeMs = snapshotAgeSource ? Math.max(0, Date.now() - new Date(snapshotAgeSource).getTime()) : NaN;
  const freshness = freshnessLabel(snapshotAgeMs);

  return (
    <section className="snapshot-health card">
      <div className="card-head">
        <h2>Snapshot Health</h2>
        <span>{freshness}</span>
      </div>
      <div className="snapshot-health-grid">
        <Stat label="Snapshot Age" value={formatAge(snapshotAgeSource)} tone={freshness === "fresh" ? "good" : freshness === "warm" ? "gold" : "bad"} />
        <Stat label="Response Time" value={formatDuration(loadDurationMs)} tone="blue" />
        <Stat label="Data Freshness" value={freshness} tone={freshness === "fresh" ? "good" : freshness === "warm" ? "gold" : "bad"} />
        <Stat label="Backend Dependency" value={backendDependencyStatus} tone={backendDependencyStatus === "healthy" || backendDependencyStatus === "ok" ? "good" : "bad"} />
      </div>
      <div className="snapshot-health-footer">
        <div><b>Fetched:</b> {lastUpdated ? lastUpdated.toLocaleTimeString() : "loading"}</div>
        <div><b>Generated:</b> {snapshotGeneratedAt ? new Date(snapshotGeneratedAt).toLocaleTimeString() : "unknown"}</div>
        <div><b>System:</b> {systemOn ? "on" : "off"}</div>
      </div>
    </section>
  );
}

function TrendCardsPanel() {
  const metrics = [
    { label: "RFQs harvested", short: "harvested" },
    { label: "Quotes submitted", short: "submitted" },
    { label: "Estimated profit", short: "profit" },
    { label: "Province activity", short: "province" },
  ];
  const windows = ["7-day", "30-day"];

  return (
    <section className="trend-cards card">
      <div className="card-head">
        <h2>Trend Cards</h2>
        <span>History not yet available</span>
      </div>
      <div className="trend-cards-grid">
        {metrics.map((metric) => (
          <div key={metric.short} className="trend-card">
            <div className="trend-card-head">
              <strong>{metric.label}</strong>
              <span>status: insufficient_history</span>
            </div>
            <div className="trend-card-window-grid">
              {windows.map((window) => (
                <div key={`${metric.short}-${window}`} className="trend-card-window">
                  <span>{window}</span>
                  <b>insufficient_history</b>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="trend-cards-footer">
        <div><b>7-day:</b> waiting for reliable snapshot history</div>
        <div><b>30-day:</b> waiting for reliable snapshot history</div>
      </div>
    </section>
  );
}

function TopActionsTodayPanel({ recommendations = {} }) {
  const status = String(recommendations.status || "insufficient_history").toLowerCase();
  const items = Array.isArray(recommendations.items) ? recommendations.items.slice(0, 4) : [];

  return (
    <section className="top-actions card" aria-label="Mission Control top actions today">
      <div className="card-head">
        <h2>Top Actions Today</h2>
        <span>{status === "configured" ? `${items.length} ready` : "insufficient history"}</span>
      </div>
      <div className="top-actions-grid">
        {items.length ? items.map((item, index) => {
          const route = item.targetRoute || "/review";
          const reasons = Array.isArray(item.reasons) ? item.reasons.slice(0, 2) : [];
          return (
            <Link key={item.id || index} className="top-action" to={route}>
              <div className="top-action-head">
                <strong>{item.title || "Action"}</strong>
                <span>{String(item.priority || "low").toUpperCase()}</span>
              </div>
              <p>{item.description || "Read-only recommendation from the snapshot."}</p>
              <div className="top-action-meta">
                <span>{item.type || "recommendation"}</span>
                <span>{item.recommendedAction || "review"}</span>
                <span>{item.relatedRfqId || "n/a"}</span>
              </div>
              <div className="top-action-stats">
                <b>{Number(item.score || 0).toFixed(0)} score</b>
                <b>{money(item.estimatedProfit || 0)}</b>
              </div>
              <div className="top-action-reasons">
                {(reasons.length ? reasons : ["No reasons supplied"]).map((reason, reasonIndex) => (
                  <small key={reasonIndex}>{reason}</small>
                ))}
              </div>
            </Link>
          );
        }) : (
          <div className="top-actions-empty">
            <strong>Insufficient history</strong>
            <span>Recommendation generation stays read-only until snapshot history is reliable.</span>
          </div>
        )}
      </div>
    </section>
  );
}

function SparkLine({ values = [] }) {
  const safe = values.length ? values : [1, 2, 1, 3, 2, 4, 3];
  const max = Math.max(...safe, 1);
  const points = safe.map((v, i) => `${(i / Math.max(1, safe.length - 1)) * 100},${36 - (v / max) * 30}`).join(" ");
  return <svg className="spark" viewBox="0 0 100 40" preserveAspectRatio="none"><polyline points={points} /></svg>;
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
    <section className="lifecycle card">
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

export default function MissionControlPage() {
  const [state, setState] = useState({ snapshot: null, loading: true, lastUpdated: null, loadDurationMs: null });
  const [busy, setBusy] = useState(false);

  async function load() {
    const started = Date.now();
    const snapshot = await fetchMissionControlSnapshot();
    setState({ snapshot, loading: false, lastUpdated: new Date(), loadDurationMs: Date.now() - started });
  }

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  const snapshot = state.snapshot || {
    portals: [],
    harvestedCount: 0,
    provinceDistribution: Object.fromEntries(provinces.map((p) => [p, 0])),
    radar: {},
    pipelineStages: { Harvested: 0, Ready: 0, "Quote Pack": 0, Submitted: 0, Blocked: 0 },
    aiScoring: { status: "not_configured", items: [] },
    quoteIntelligence: {
      supplierCoverage: 0,
      pricingFreshness: 0,
      awardSignals: 0,
      competitorSignals: 0,
      status: "insufficient_history",
    },
    recommendations: {
      status: "insufficient_history",
      generatedAt: "",
      items: [],
    },
    opportunities: [],
    lifecycle: {},
    lifecycleAnalytics: {},
    lifecycleTelemetry: {},
    policy: {},
    auto: {},
    metrics: {
      backendStatus: "unknown",
      displayMode: "controlled",
      systemOn: true,
      quoteReadyCount: 0,
      submittedCount: 0,
      blockedCount: 0,
      profitTotal: 0,
      trend: [
        { label: "D", value: 0 },
        { label: "W", value: 0 },
        { label: "M", value: 0 },
      ],
      alerts: [],
      portalStatus: "fallback",
      topOpps: [],
    },
  };
  const metrics = snapshot.metrics || {};
  const topOpps = metrics.topOpps || snapshot.opportunities.slice(0, 9);
  const portalList = snapshot.portals || [];
  const alerts = metrics.alerts || [];
  const systemOn = Boolean(metrics.systemOn);
  const backendStatus = metrics.backendStatus || "unknown";
  const displayMode = metrics.displayMode || "controlled";
  const harvested = snapshot.harvestedCount || 0;
  const quoteReady = metrics.quoteReadyCount || 0;
  const submitted = metrics.submittedCount || 0;
  const blocked = metrics.blockedCount || 0;
  const profitTotal = metrics.profitTotal || 0;
  const trend = metrics.trend || [];
  const stageCounts = snapshot.pipelineStages || {};
  const provinceCounts = snapshot.provinceDistribution || {};
  const radarPayload = snapshot.radar || {};
  const lifecycle = snapshot.lifecycle || {};
  const telemetry = snapshot.lifecycleTelemetry || {};

  async function toggleSystem() {
    setBusy(true);
    const currentPolicy = snapshot.policy?.policy || { enabled: systemOn, mode: "controlled", allow_email_send: false, allow_portal_upload: true, allow_portal_final_submit: true };
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

  return (
    <div className="mission-control-page">
      <div className="dashboard-shell">
        <section className="hero card">
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

        <section className="quick-actions card" aria-label="Mission Control quick actions">
          <div className="card-head">
            <h2>Quick Actions</h2>
            <span>Read-only navigation</span>
          </div>
          <div className="quick-actions-grid">
            {quickActions.map((action) => (
              <Link key={action.label} className="quick-action-link" to={action.to}>
                <strong>{action.label}</strong>
                <span>{action.description}</span>
              </Link>
            ))}
          </div>
        </section>

        <SnapshotHealthPanel
          snapshot={snapshot}
          lastUpdated={state.lastUpdated}
          loadDurationMs={state.loadDurationMs}
          backendStatus={backendStatus}
          systemOn={systemOn}
        />

        <TrendCardsPanel />

        <MissionControlQuoteIntelligencePanel quoteIntelligence={snapshot.quoteIntelligence || {}} />

        <TopActionsTodayPanel recommendations={snapshot.recommendations || {}} />

        <section className="main-grid">
          <div className="card radar">
            <div className="card-head"><h2>Radar</h2><span>{radarPayload.serviceVersion || radarPayload.statusLabel || "active"}</span></div>
            <div className="radar-scope"><i /><i /><i /><b /></div>
            <div className="radar-stats"><Stat label="Sources" value={compact(radarPayload.sources || 0)} /><Stat label="Eligible" value={compact(radarPayload.eligible || quoteReady)} /></div>
          </div>

          <div className="card heatmap">
            <div className="card-head"><h2>South Africa Heatmap</h2><span>Province opportunity density</span></div>
            <div className="province-grid">{provinces.map((p) => <div className="province" key={p}><b>{p}</b><span>{provinceCounts[p] || 0}</span><em style={{ opacity: Math.min(.95, .25 + (provinceCounts[p] || 0) / Math.max(1, harvested)) }} /></div>)}</div>
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

        <section className="lanes card">
          <div className="card-head"><h2>Tender Lanes</h2><span>Harvest → Ready → Pack → Submit</span></div>
          <div className="lane-grid">{Object.entries(stageCounts).map(([name, count]) => <div className="lane" key={name}><strong>{name}</strong><b>{count}</b><small>{name === "Submitted" ? "delivered" : name === "Blocked" ? "needs review" : "processing"}</small></div>)}</div>
        </section>

        <MissionControlAiScoringPanel aiScoring={snapshot.aiScoring || {}} />

        <LifecyclePanel lifecycle={lifecycle} analytics={snapshot.lifecycleAnalytics} telemetry={telemetry} />

        <BusinessIntelligenceExpansionPackPanel />

        <section className="bottom-grid">
          <div className="card table-card">
            <div className="card-head"><h2>Live Tender Stream</h2><span>{topOpps.length} visible</span></div>
            <table><thead><tr><th>RFQ</th><th>Buyer</th><th>Province</th><th>Stage</th><th>Profit</th></tr></thead><tbody>{topOpps.map((x, i) => <tr key={i}><td>{x.buyerRfqNumber}</td><td>{x.buyerName}</td><td>{x.province}</td><td><span className="pill">{x.stage}</span></td><td>{money(x.profit)}</td></tr>)}</tbody></table>
          </div>

          <div className="card portal-card">
            <div className="card-head"><h2>Portal Health</h2><span>{metrics.portalStatus || (portalList.length ? "live" : "fallback")}</span></div>
            <div className="portal-list">{portalList.map((p, i) => <div key={i}><b>{p.name}</b><span>{p.status}</span></div>)}</div>
          </div>

          <div className="card alerts-card">
            <div className="card-head"><h2>Alerts</h2><span>{alerts.length || 0}</span></div>
            <div className="alerts">{(alerts.length ? alerts : ["No critical alerts detected"]).map((a, i) => <p key={i}>{a}</p>)}</div>
          </div>
        </section>
        <LiveSubmissionFeedPanel refreshMs={10000} />
      </div>
    </div>
  );
}
