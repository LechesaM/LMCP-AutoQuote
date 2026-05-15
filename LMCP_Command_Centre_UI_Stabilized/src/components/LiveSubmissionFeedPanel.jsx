import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  getHealth,
  getPortalSubmissionStatus,
  getProductionLockStatus,
  getProofCenter,
  notify,
  proofDownloadUrl,
  proofScreenshotUrl,
  requestBrowserNotifications,
} from "../services/liveDashboardAlertsService";

function toneForStatus(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("submitted") || value === "ok" || value.includes("healthy") || value.includes("allowed")) return "success";
  if (value.includes("blocked") || value.includes("failed") || value.includes("error")) return "danger";
  if (value.includes("assist") || value.includes("pending") || value.includes("warning") || value.includes("verification")) return "warning";
  return "neutral";
}

function Badge({ children, tone = "neutral" }) {
  return <span className={`ops-badge ${tone}`}>{children}</span>;
}

function formatTime(value) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString("en-ZA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function compactText(value, limit = 64) {
  const text = String(value || "UNKNOWN");
  return text.length > limit ? `${text.slice(0, limit - 3)}...` : text;
}

function safeRecords(value) {
  return Array.isArray(value) ? value : [];
}

function FeedMetric({ label, value, tone = "neutral" }) {
  return (
    <div className={`feed-metric ${tone}`}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

export default function LiveSubmissionFeedPanel({ refreshMs = 10000 }) {
  const [health, setHealth] = useState(null);
  const [portal, setPortal] = useState(null);
  const [proofs, setProofs] = useState(null);
  const [productionLock, setProductionLock] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("Starting live feed...");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [busy, setBusy] = useState(false);
  const seenRef = useRef(new Set());
  const firstLoadRef = useRef(true);

  const proofRecords = safeRecords(proofs?.records).slice(0, 25);
  const portalHistory = safeRecords(
    portal?.recent_history ||
      portal?.history ||
      portal?.records ||
      portal?.recent_submissions
  ).slice(0, 12);
  const productionDecisions = safeRecords(productionLock?.recent_decisions).slice(0, 20);

  function pushAlert(alert) {
    const id = `${alert.type || "alert"}-${alert.key || alert.message}-${Date.now()}`;
    const item = { id, created_at: new Date().toISOString(), ...alert };
    setAlerts((prev) => [item, ...prev].slice(0, 20));

    if (!firstLoadRef.current) {
      notify(alert.title || "LMCP Alert", alert.message || "New system event detected.");
    }
  }

  async function loadLiveData({ manual = false } = {}) {
    setBusy(true);
    try {
      const [healthResult, portalResult, proofResult, lockResult] = await Promise.allSettled([
        getHealth(),
        getPortalSubmissionStatus(25),
        getProofCenter(25),
        getProductionLockStatus(25),
      ]);

      if (healthResult.status === "fulfilled") setHealth(healthResult.value);
      if (portalResult.status === "fulfilled") setPortal(portalResult.value);
      if (proofResult.status === "fulfilled") setProofs(proofResult.value);
      if (lockResult.status === "fulfilled") setProductionLock(lockResult.value);

      const failures = [healthResult, portalResult, proofResult, lockResult].filter((r) => r.status === "rejected");
      setStatus(
        failures.length
          ? `Live feed online with ${failures.length} warning(s).`
          : `Live feed refreshed at ${new Date().toLocaleTimeString()}.`
      );

      if (healthResult.status === "fulfilled") {
        const failedCount = Number(healthResult.value?.failed_routers_count || 0);
        const key = `health-failed-routers-${failedCount}`;
        if (failedCount > 0 && !seenRef.current.has(key)) {
          seenRef.current.add(key);
          pushAlert({ type: "warning", tone: "warning", title: "Router warnings detected", message: `${failedCount} optional router warning(s) found.`, key });
        }
      }

      if (proofResult.status === "fulfilled") {
        for (const record of safeRecords(proofResult.value?.records)) {
          const key = `proof-${record.record_id}`;
          if (!seenRef.current.has(key)) {
            seenRef.current.add(key);
            if (!firstLoadRef.current && record.submitted) {
              pushAlert({ type: "proof", tone: "success", title: "Submission proof captured", message: `${record.buyer_rfq_number || "RFQ"} / ${record.quote_number || "Quote"}`, key });
            }
          }
        }
      }

      if (lockResult.status === "fulfilled") {
        for (const decision of safeRecords(lockResult.value?.recent_decisions)) {
          const key = `lock-${decision.checked_at}-${decision.status}-${JSON.stringify(decision.payload_keys || [])}`;
          if (!seenRef.current.has(key)) {
            seenRef.current.add(key);
            if (!firstLoadRef.current && decision.status === "blocked") {
              pushAlert({ type: "blocked", tone: "danger", title: "Submission blocked by Production Lock", message: decision.reasons?.[0]?.message || "A submission was blocked.", key });
            }
          }
        }
      }

      if (manual) {
        pushAlert({ type: "manual_refresh", tone: "neutral", title: "Manual refresh completed", message: "Dashboard live data was refreshed.", key: `manual-${Date.now()}` });
      }

      firstLoadRef.current = false;
    } catch (error) {
      setStatus(error.message || "Live feed refresh failed.");
      pushAlert({ type: "error", tone: "danger", title: "Live feed error", message: error.message || "Unable to refresh live data.", key: `error-${Date.now()}` });
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadLiveData();
    if (!autoRefresh) return undefined;
    const timer = setInterval(() => loadLiveData(), refreshMs);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, refreshMs]);

  const summary = useMemo(() => {
    const submittedProofs = proofRecords.filter((p) => p.submitted).length;
    const blocked = productionDecisions.filter((d) => d.status === "blocked").length;
    return {
      submittedProofs,
      blocked,
      proofTotal: proofRecords.length,
      routerWarnings: Number(health?.failed_routers_count || 0),
    };
  }, [proofRecords, productionDecisions, health]);

  return (
    <section className="live-feed card">
      <div className="feed-head">
        <div>
          <p className="eyebrow">Live operations</p>
          <h2>Live Submission Feed & Alerts</h2>
          <p className="muted">Auto-refreshing proofs, Production Lock decisions, and backend warnings.</p>
        </div>
        <div className="feed-actions">
          <button onClick={() => requestBrowserNotifications()}>Enable alerts</button>
          <button className={autoRefresh ? "active" : ""} onClick={() => setAutoRefresh((v) => !v)}>{autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}</button>
          <button className="primary" onClick={() => loadLiveData({ manual: true })} disabled={busy}>{busy ? "Refreshing..." : "Refresh now"}</button>
        </div>
      </div>

      <div className="feed-metrics">
        <FeedMetric label="Submitted proofs" value={summary.submittedProofs} tone="success" />
        <FeedMetric label="Proof records" value={summary.proofTotal} />
        <FeedMetric label="Blocked decisions" value={summary.blocked} tone={summary.blocked ? "danger" : "neutral"} />
        <FeedMetric label="Router warnings" value={summary.routerWarnings} tone={summary.routerWarnings ? "warning" : "success"} />
      </div>

      <div className="feed-status">
        <span>{status}</span>
        <Badge tone={autoRefresh ? "success" : "neutral"}>Every {Math.round(refreshMs / 1000)}s</Badge>
      </div>

      <div className="feed-grid">
        <div className="feed-panel">
          <div className="feed-panel-head"><h3>Latest proof records</h3><Badge>{proofRecords.length} visible</Badge></div>
          <div className="feed-scroll">
            {proofRecords.length === 0 ? <p className="empty">No proof records found yet.</p> : proofRecords.map((record) => (
              <article key={record.record_id || `${record.buyer_rfq_number}-${record.created_at}`} className="proof-row">
                <div className="proof-main">
                  <div>
                    <h4>{compactText(record.buyer_rfq_number || record.rfq_number || record.title)}</h4>
                    <p>{record.quote_number || record.record_id || "No quote number"}</p>
                    <small>{formatTime(record.created_at || record.submitted_at)}</small>
                  </div>
                  <Badge tone={record.submitted ? "success" : toneForStatus(record.submission_status)}>{record.submission_status || (record.submitted ? "submitted" : "pending")}</Badge>
                </div>
                <div className="proof-actions">
                  {record.record_id && <a href={proofDownloadUrl(record.record_id)} target="_blank" rel="noreferrer">Proof JSON</a>}
                  {record.record_id && record.screenshot_count > 0 && <a className="ghost" href={proofScreenshotUrl(record.record_id, 0)} target="_blank" rel="noreferrer">Screenshot</a>}
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="feed-panel">
          <div className="feed-panel-head"><h3>Alerts</h3><Badge tone={alerts.length ? "warning" : "success"}>{alerts.length}</Badge></div>
          <div className="feed-scroll">
            {alerts.length === 0 ? <p className="alert-empty">No new alerts in this session.</p> : alerts.map((alert) => (
              <article key={alert.id} className="alert-row">
                <div>
                  <h4>{alert.title}</h4>
                  <p>{alert.message}</p>
                  <small>{formatTime(alert.created_at)}</small>
                </div>
                <Badge tone={alert.tone}>{alert.type}</Badge>
              </article>
            ))}
          </div>
        </div>
      </div>

      {portalHistory.length > 0 && (
        <div className="feed-panel portal-history">
          <div className="feed-panel-head"><h3>Portal submission history</h3><Badge>{portalHistory.length} rows</Badge></div>
          <div className="history-table">
            {portalHistory.map((item, index) => (
              <div key={`${item.buyer_rfq_number || item.rfq_number || "rfq"}-${index}`}>
                <b>{compactText(item.buyer_rfq_number || item.rfq_number)}</b>
                <span>{item.quote_number || "-"}</span>
                <Badge tone={toneForStatus(item.submission_status || item.status)}>{item.submission_status || item.status || "unknown"}</Badge>
                <small>{formatTime(item.submitted_at || item.finished_at || item.started_at)}</small>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
