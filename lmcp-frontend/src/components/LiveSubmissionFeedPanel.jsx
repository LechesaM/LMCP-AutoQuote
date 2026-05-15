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
  const cls = {
    success: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    danger: "border-rose-400/40 bg-rose-400/10 text-rose-300",
    warning: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    neutral: "border-slate-500/50 bg-slate-400/10 text-slate-300",
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide ${cls[tone] || cls.neutral}`}>
      {children}
    </span>
  );
}

function formatTime(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function compactId(value, limit = 46) {
  const text = String(value || "UNKNOWN");
  return text.length > limit ? `${text.slice(0, limit - 3)}...` : text;
}

function safeRecords(value) {
  return Array.isArray(value) ? value : [];
}

function MetricCard({ label, value, tone = "neutral" }) {
  const toneCls = {
    success: "text-emerald-300",
    danger: "text-rose-300",
    warning: "text-amber-300",
    neutral: "text-slate-100",
  };

  return (
    <div className="rounded-2xl border border-slate-700/70 bg-slate-900/55 px-4 py-3 shadow-inner shadow-black/20">
      <div className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-black ${toneCls[tone] || toneCls.neutral}`}>{value}</div>
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
          pushAlert({
            type: "warning",
            tone: "warning",
            title: "Router warnings detected",
            message: `${failedCount} optional router warning(s) found.`,
            key,
          });
        }
      }

      if (proofResult.status === "fulfilled") {
        for (const record of safeRecords(proofResult.value?.records)) {
          const key = `proof-${record.record_id}`;
          if (!seenRef.current.has(key)) {
            seenRef.current.add(key);
            if (!firstLoadRef.current && record.submitted) {
              pushAlert({
                type: "proof",
                tone: "success",
                title: "Submission proof captured",
                message: `${record.buyer_rfq_number || "RFQ"} / ${record.quote_number || "Quote"}`,
                key,
              });
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
              pushAlert({
                type: "blocked",
                tone: "danger",
                title: "Submission blocked by Production Lock",
                message: decision.reasons?.[0]?.message || "A submission was blocked.",
                key,
              });
            }
          }
        }
      }

      if (manual) {
        pushAlert({
          type: "manual_refresh",
          tone: "neutral",
          title: "Manual refresh completed",
          message: "Dashboard live data was refreshed.",
          key: `manual-${Date.now()}`,
        });
      }

      firstLoadRef.current = false;
    } catch (error) {
      setStatus(error.message || "Live feed refresh failed.");
      pushAlert({
        type: "error",
        tone: "danger",
        title: "Live feed error",
        message: error.message || "Unable to refresh live data.",
        key: `error-${Date.now()}`,
      });
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
    <section className="rounded-3xl border border-slate-700/70 bg-slate-950/70 p-4 shadow-2xl shadow-black/30 backdrop-blur">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-300">Live operations</div>
          <h2 className="mt-1 text-xl font-black text-slate-100">Live Submission Feed & Alerts</h2>
          <p className="text-xs text-slate-400">Auto-refreshing proofs, Production Lock decisions, and backend warnings.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => requestBrowserNotifications()}
            className="rounded-2xl border border-slate-600 bg-slate-900/70 px-4 py-2 text-xs font-black text-slate-200 hover:border-emerald-400/70"
          >
            Enable alerts
          </button>
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`rounded-2xl px-4 py-2 text-xs font-black ${autoRefresh ? "bg-emerald-500 text-slate-950" : "bg-slate-700 text-slate-200"}`}
          >
            {autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}
          </button>
          <button
            onClick={() => loadLiveData({ manual: true })}
            disabled={busy}
            className="rounded-2xl bg-blue-500 px-4 py-2 text-xs font-black text-white disabled:opacity-60"
          >
            {busy ? "Refreshing..." : "Refresh now"}
          </button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <MetricCard label="Submitted proofs" value={summary.submittedProofs} tone="success" />
        <MetricCard label="Proof records" value={summary.proofTotal} />
        <MetricCard label="Blocked decisions" value={summary.blocked} tone={summary.blocked ? "danger" : "neutral"} />
        <MetricCard label="Router warnings" value={summary.routerWarnings} tone={summary.routerWarnings ? "warning" : "success"} />
      </div>

      <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/50 px-4 py-2">
        <div className="truncate text-xs text-slate-400">{status}</div>
        <Badge tone={autoRefresh ? "success" : "neutral"}>Every {Math.round(refreshMs / 1000)}s</Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900/45">
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-700/70 bg-slate-900/95 px-4 py-3">
            <div className="font-black text-slate-100">Latest proof records</div>
            <Badge tone="neutral">{proofRecords.length} visible</Badge>
          </div>
          <div className="max-h-[390px] overflow-auto">
            {proofRecords.length === 0 ? (
              <div className="p-4 text-sm text-slate-400">No proof records found yet.</div>
            ) : (
              proofRecords.map((record) => (
                <div key={record.record_id || `${record.buyer_rfq_number}-${record.created_at}`} className="border-b border-slate-800/80 p-4 last:border-b-0 hover:bg-slate-800/35">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-black text-slate-100">{compactId(record.buyer_rfq_number || record.rfq_number || record.title)}</div>
                      <div className="mt-1 truncate text-xs text-slate-400">{record.quote_number || record.record_id || "No quote number"}</div>
                      <div className="mt-1 text-[11px] text-slate-500">{formatTime(record.created_at || record.submitted_at)}</div>
                    </div>
                    <Badge tone={record.submitted ? "success" : toneForStatus(record.submission_status)}>
                      {record.submission_status || (record.submitted ? "submitted" : "pending")}
                    </Badge>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {record.record_id && (
                      <a href={proofDownloadUrl(record.record_id)} target="_blank" rel="noreferrer" className="rounded-xl bg-slate-100 px-3 py-2 text-[11px] font-black text-slate-950">
                        Proof JSON
                      </a>
                    )}
                    {record.record_id && record.screenshot_count > 0 && (
                      <a href={proofScreenshotUrl(record.record_id, 0)} target="_blank" rel="noreferrer" className="rounded-xl border border-slate-600 px-3 py-2 text-[11px] font-black text-slate-200">
                        Screenshot
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900/45">
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-700/70 bg-slate-900/95 px-4 py-3">
            <div className="font-black text-slate-100">Alerts</div>
            <Badge tone={alerts.length ? "warning" : "success"}>{alerts.length}</Badge>
          </div>
          <div className="max-h-[390px] overflow-auto">
            {alerts.length === 0 ? (
              <div className="m-4 rounded-2xl border border-amber-400/25 bg-amber-400/10 p-4 text-sm font-bold text-amber-200">No new alerts in this session.</div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="border-b border-slate-800/80 p-4 last:border-b-0 hover:bg-slate-800/35">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-black text-slate-100">{alert.title}</div>
                      <div className="mt-1 text-xs text-slate-400">{alert.message}</div>
                      <div className="mt-1 text-[11px] text-slate-500">{formatTime(alert.created_at)}</div>
                    </div>
                    <Badge tone={alert.tone}>{alert.type}</Badge>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {portalHistory.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900/45">
          <div className="border-b border-slate-700/70 bg-slate-900/95 px-4 py-3 font-black text-slate-100">Portal submission history</div>
          <div className="max-h-[280px] overflow-auto">
            {portalHistory.map((item, index) => (
              <div key={`${item.buyer_rfq_number || item.rfq_number || "rfq"}-${index}`} className="grid gap-2 border-b border-slate-800/80 p-4 text-xs last:border-b-0 md:grid-cols-4">
                <div className="font-black text-slate-100">{compactId(item.buyer_rfq_number || item.rfq_number)}</div>
                <div className="text-slate-400">{item.quote_number || "—"}</div>
                <div><Badge tone={toneForStatus(item.submission_status || item.status)}>{item.submission_status || item.status || "unknown"}</Badge></div>
                <div className="text-slate-500">{formatTime(item.submitted_at || item.finished_at || item.started_at)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
