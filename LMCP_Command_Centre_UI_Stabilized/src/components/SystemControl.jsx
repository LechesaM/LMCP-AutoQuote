import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Play,
  Power,
  RefreshCw,
  ShieldAlert,
  Square,
} from "lucide-react";

import {
  API_BASE,
  emergencyStop,
  getSystemStatus,
  pauseHarvesting,
  pauseSubmissions,
  resumeAll,
  runOneAutonomousCycle,
  turnSystemOff,
  turnSystemOn,
} from "../services/systemControl";

import "./SystemControl.css";

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

function StatusPill({ enabled, status }) {
  return (
    <span className={`lmcp-status-pill ${enabled ? "on" : "off"}`}>
      <span className="dot" />
      {enabled ? "SYSTEM ON" : "SYSTEM OFF"} <span className="separator">•</span>{" "}
      {String(status || "unknown").toUpperCase()}
    </span>
  );
}

function MetricCard({ label, value, helper }) {
  return (
    <div className="lmcp-control-metric">
      <p>{label}</p>
      <strong>{value}</strong>
      {helper ? <span>{helper}</span> : null}
    </div>
  );
}

export default function SystemControl({ autoRefreshMs = 15000 }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [lastAction, setLastAction] = useState("");
  const [error, setError] = useState("");

  const enabled = Boolean(status?.enabled);

  const processed = useMemo(() => {
    return status?.processed ?? 0;
  }, [status]);

  async function refreshStatus(silent = false) {
    if (!silent) {
      setBusy(true);
      setError("");
    }

    try {
      const nextStatus = await getSystemStatus();
      setStatus(nextStatus);
      if (!silent) setLastAction("Status refreshed.");
    } catch (err) {
      setError(err.message || "Could not load system status.");
    } finally {
      if (!silent) setBusy(false);
    }
  }

  useEffect(() => {
    refreshStatus(true);

    const timer = setInterval(() => {
      refreshStatus(true);
    }, autoRefreshMs);

    return () => clearInterval(timer);
  }, [autoRefreshMs]);

  async function handleAction(label, action) {
    setBusy(true);
    setError("");
    setLastAction("");

    try {
      const result = await action();
      setLastAction(`${label} completed via ${result?._resolved_path || "backend"}.`);
      await refreshStatus(true);
    } catch (err) {
      setError(err.message || `${label} failed.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="lmcp-system-control">
      <div className="lmcp-control-header">
        <div>
          <p className="lmcp-step">STEP 7</p>
          <h2>ON/OFF System Control</h2>
          <p className="lmcp-control-subtitle">
            Control the autonomous LMCP engine directly from the dashboard, monitor live system
            status, and trigger an immediate run when needed.
          </p>

          <div className="lmcp-control-badges">
            <StatusPill enabled={enabled} status={status?.last_status || "loading"} />
            <span className="lmcp-refresh-pill">
              <Clock size={16} />
              Live refreshed: {formatDateTime(status?.updated_at)}
            </span>
          </div>

          <p className="lmcp-backend-url">Backend base URL: {API_BASE}</p>
        </div>

        <div className="lmcp-control-actions">
          <button
            className="lmcp-btn green"
            disabled={busy}
            onClick={() => handleAction("Turn System ON", turnSystemOn)}
          >
            <Power size={18} />
            Turn System ON
          </button>

          <button
            className="lmcp-btn red"
            disabled={busy}
            onClick={() => handleAction("Turn System OFF", turnSystemOff)}
          >
            <Square size={18} />
            Turn System OFF
          </button>

          <button
            className="lmcp-btn cyan"
            disabled={busy || !enabled}
            onClick={() => handleAction("Run One Cycle", runOneAutonomousCycle)}
          >
            <Play size={18} />
            Run One Cycle
          </button>

          <button className="lmcp-btn dark" disabled={busy} onClick={() => refreshStatus()}>
            <RefreshCw size={18} className={busy ? "spin" : ""} />
            Refresh Status
          </button>
        </div>
      </div>

      {error ? (
        <div className="lmcp-alert error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      ) : null}

      {lastAction ? (
        <div className="lmcp-alert success">
          <CheckCircle2 size={18} />
          <span>{lastAction}</span>
        </div>
      ) : null}

      <div className="lmcp-control-grid">
        <MetricCard label="Enabled" value={enabled ? "YES" : "NO"} helper="Autonomous engine flag" />
        <MetricCard
          label="Last Status"
          value={String(status?.last_status || "LOADING").toUpperCase()}
          helper="Latest engine state"
        />
        <MetricCard label="Last Run" value={formatDateTime(status?.last_run_at)} helper="Most recent autonomous run" />
        <MetricCard label="Updated" value={formatDateTime(status?.updated_at)} helper="Latest status refresh" />
        <MetricCard label="Processed" value={processed} helper="Last result item count" />
      </div>

      <div className="lmcp-control-lower">
        <div className="lmcp-control-panel">
          <h3>System Summary</h3>

          <div className="lmcp-summary-grid">
            <div>
              <h4>Last Message</h4>
              <p>{status?.last_message || "Loading system status..."}</p>
            </div>

            <div>
              <h4>Last Successful Items</h4>
              <strong>{processed}</strong>
              <p>Derived from last_result when available.</p>
            </div>
          </div>

          <h4>Raw Status Snapshot</h4>
          <pre>{JSON.stringify(status?.raw || {}, null, 2)}</pre>
        </div>

        <div className="lmcp-control-panel">
          <h3>Control Notes</h3>

          <div className="lmcp-note">
            <h4>Turn System ON</h4>
            <p>Calls <code>/system/control/on</code> with fallback support for older autonomous endpoints.</p>
          </div>

          <div className="lmcp-note">
            <h4>Turn System OFF</h4>
            <p>Calls <code>/system/control/off</code> and stops future autonomous activity.</p>
          </div>

          <div className="lmcp-note">
            <h4>Run One Cycle</h4>
            <p>Calls <code>/autonomous/run-once</code> so you can trigger one immediate engine run.</p>
          </div>

          <div className="lmcp-danger-row">
            <button
              className="lmcp-mini-btn orange"
              disabled={busy}
              onClick={() => handleAction("Pause Harvesting", pauseHarvesting)}
            >
              Pause Harvest
            </button>

            <button
              className="lmcp-mini-btn orange"
              disabled={busy}
              onClick={() => handleAction("Pause Submissions", pauseSubmissions)}
            >
              Pause Submissions
            </button>

            <button
              className="lmcp-mini-btn green"
              disabled={busy}
              onClick={() => handleAction("Resume All", resumeAll)}
            >
              Resume All
            </button>

            <button
              className="lmcp-mini-btn red"
              disabled={busy}
              onClick={() => handleAction("Emergency Stop", emergencyStop)}
            >
              <ShieldAlert size={16} />
              Emergency Stop
            </button>
          </div>
        </div>
      </div>

      <div className="lmcp-control-footer">
        <Activity size={16} />
        <span>Status endpoint used: {status?.resolved_path || "detecting..."}</span>
      </div>
    </section>
  );
}
