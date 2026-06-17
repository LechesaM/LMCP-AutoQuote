import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Play,
  RefreshCw,
  Send,
  Zap,
} from "lucide-react";

import {
  API_BASE,
  getPipelineSnapshot,
  normalizeCycleResult,
  runOneCycle,
} from "../services/autonomousCycle";

import "./AutonomousCycleSync.css";

function formatDateTime(value) {
  if (!value) return "—";
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("en-ZA", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch {
    return "—";
  }
}

function Metric({ label, value, helper }) {
  return (
    <div className="lmcp-step8-metric">
      <p>{label}</p>
      <strong>{value}</strong>
      {helper ? <span>{helper}</span> : null}
    </div>
  );
}

function RawBlock({ title, data }) {
  return (
    <div className="lmcp-step8-raw">
      <h4>{title}</h4>
      <pre>{JSON.stringify(data || {}, null, 2)}</pre>
    </div>
  );
}

export default function AutonomousCycleSync({ autoRefreshMs = 20000 }) {
  const [snapshot, setSnapshot] = useState(null);
  const [lastCycle, setLastCycle] = useState(null);
  const [busy, setBusy] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const dashboard = snapshot?.dashboard || {};
  const submissions = snapshot?.submissions || {};
  const profit = snapshot?.profit || {};
  const status = snapshot?.status || {};

  const summary = dashboard?.summary || dashboard || {};
  const submissionHistory =
    submissions?.submission_history || submissions?.history || submissions || {};

  const metrics = useMemo(() => {
    return {
      rfqFolders:
        summary?.rfq_folders ??
        summary?.total_opportunities ??
        summary?.opportunities ??
        summary?.count ??
        "—",
      quoteReady:
        summary?.quote_ready ??
        summary?.ready_for_quote ??
        summary?.quote_ready_count ??
        "—",
      submitted:
        submissionHistory?.submitted ??
        submissions?.submitted ??
        submissions?.total_submitted ??
        summary?.submitted ??
        "—",
      failed:
        submissionHistory?.failed ??
        submissions?.failed ??
        submissions?.total_failed ??
        summary?.failed ??
        "—",
      revenue: profit?.total_revenue ?? profit?.revenue ?? 0,
      profit: profit?.total_profit ?? profit?.profit ?? 0,
    };
  }, [summary, submissions, submissionHistory, profit]);

  // 🔁 GLOBAL BROADCAST
  function broadcastRefresh() {
    window.dispatchEvent(
      new CustomEvent("lmcp-refresh", {
        detail: {
          source: "AutonomousCycleSync",
          at: new Date().toISOString(),
        },
      })
    );
  }

  async function refreshSnapshot(silent = false) {
    if (!silent) {
      setBusy(true);
      setNotice("");
      setError("");
    }

    try {
      const data = await getPipelineSnapshot();
      setSnapshot(data);

      // 🔁 notify whole dashboard
      broadcastRefresh();

      if (!silent) setNotice("Dashboard snapshot refreshed.");
    } catch (err) {
      setError(err.message || "Failed to refresh dashboard snapshot.");
    } finally {
      if (!silent) setBusy(false);
    }
  }

  async function handleRunCycle() {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const result = await runOneCycle();
      const normalized = normalizeCycleResult(result);
      setLastCycle(normalized);

      setNotice(
        `Autonomous cycle completed via ${
          normalized.resolved_path || "backend"
        }.`
      );

      const data = await getPipelineSnapshot();
      setSnapshot(data);

      // 🔁 CRITICAL: sync whole dashboard
      broadcastRefresh();
    } catch (err) {
      setError(err.message || "Autonomous cycle failed.");
    } finally {
      setBusy(false);
    }
  }

  // initial load
  useEffect(() => {
    refreshSnapshot(true);
  }, []);

  // 🔁 LISTEN FOR OTHER PANELS
  useEffect(() => {
    const handler = (event) => {
      if (event?.detail?.source === "AutonomousCycleSync") return;
      refreshSnapshot(true);
    };

    window.addEventListener("lmcp-refresh", handler);
    return () => window.removeEventListener("lmcp-refresh", handler);
  }, []);

  // auto refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const timer = setInterval(() => {
      refreshSnapshot(true);
    }, autoRefreshMs);

    return () => clearInterval(timer);
  }, [autoRefresh]);

  return (
    <section className="lmcp-step8">
      <div className="lmcp-step8-header">
        <div>
          <p className="lmcp-step8-label">STEP 8</p>
          <h2>Autonomous Cycle Live Trigger + Dashboard Sync</h2>

          <div className="lmcp-step8-badges">
            <span className="lmcp-step8-pill">
              <Activity size={16} /> API: {API_BASE}
            </span>
            <span className="lmcp-step8-pill">
              <Clock size={16} /> Last sync:{" "}
              {formatDateTime(snapshot?.refreshed_at)}
            </span>
            <span className="lmcp-step8-pill">
              {autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
            </span>
          </div>
        </div>

        <div className="lmcp-step8-actions">
          <button onClick={handleRunCycle} disabled={busy}>
            Run One Cycle
          </button>

          <button onClick={() => refreshSnapshot()} disabled={busy}>
            Refresh Dashboard
          </button>

          <button onClick={() => setAutoRefresh(!autoRefresh)}>
            {autoRefresh ? "Pause Auto-Sync" : "Resume Auto-Sync"}
          </button>
        </div>
      </div>

      {notice && <div className="success">{notice}</div>}
      {error && <div className="error">{error}</div>}

      <div className="lmcp-step8-grid">
        <Metric label="RFQ Folders" value={metrics.rfqFolders} />
        <Metric label="Quote Ready" value={metrics.quoteReady} />
        <Metric label="Submitted" value={metrics.submitted} />
        <Metric label="Failed" value={metrics.failed} />
      </div>
    </section>
  );
}
