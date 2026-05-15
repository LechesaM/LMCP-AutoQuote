import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Play, RefreshCw, Rocket, ShieldCheck } from "lucide-react";
import {
  API_BASE,
  getFinalAutomationStatus,
  runFinalAutomationOnce,
  runGoLiveCheck,
} from "../services/finalAutomation";

function Badge({ children, tone }) {
  const cls =
    tone === "good"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : tone === "warn"
      ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
      : "border-rose-500/20 bg-rose-500/10 text-rose-300";

  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${cls}`}>{children}</span>;
}

function Stat({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 break-all text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

export default function FinalAutomationPanel() {
  const [status, setStatus] = useState(null);
  const [lastRun, setLastRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const ready = status?.ready_for_live_automation || status?.status === "ready";
  const compliance = status?.compliance || {};
  const blockers = status?.blockers || [];

  const availableDocs = useMemo(() => {
    return Object.keys(compliance?.available_documents || {}).length;
  }, [compliance]);

  async function refresh() {
    setBusy(true);
    setNotice("");
    setError("");

    try {
      const data = await getFinalAutomationStatus();
      setStatus(data);
      setNotice("Final automation status refreshed.");
    } catch (err) {
      setError(err.message || "Could not load final automation status.");
    } finally {
      setBusy(false);
    }
  }

  async function check() {
    setBusy(true);
    setNotice("");
    setError("");

    try {
      const data = await runGoLiveCheck();
      setStatus(data);
      setNotice(data.status === "ready" ? "Go-live check passed." : "Go-live check found blockers.");
      window.dispatchEvent(new CustomEvent("lmcp-refresh", { detail: { source: "FinalAutomationPanel" } }));
    } catch (err) {
      setError(err.message || "Go-live check failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runOnce() {
    setBusy(true);
    setNotice("");
    setError("");

    try {
      const data = await runFinalAutomationOnce({ test_mode: false });
      setLastRun(data);
      setNotice(data.status === "ok" ? "Final automation run completed." : `Final automation: ${data.status}`);
      await refresh();
      window.dispatchEvent(new CustomEvent("lmcp-refresh", { detail: { source: "FinalAutomationPanel" } }));
    } catch (err) {
      setError(err.message || "Final automation run failed.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-emerald-300">Final Layer</div>
          <h2 className="mt-2 text-2xl font-semibold">Final Automation Control</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Production guardrail for live automation: checks compliance, CSD readiness, autonomous status, then runs one safe automation cycle.
          </p>
          <div className="mt-3 text-xs text-slate-500">API: {API_BASE}</div>
        </div>

        <Badge tone={ready ? "good" : "danger"}>
          {ready ? "READY FOR LIVE AUTOMATION" : "BLOCKED"}
        </Badge>
      </div>

      {notice ? (
        <div className="mt-4 flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <CheckCircle2 size={16} />
          {notice}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 flex items-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          <AlertTriangle size={16} />
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <Stat label="Go-Live Status" value={status?.status || "checking"} />
        <Stat label="Compliance Docs" value={availableDocs} />
        <Stat label="Missing Required" value={(compliance?.missing_required || []).join(", ") || "None"} />
        <Stat label="CSD Report" value={status?.csd?.standard_csd_report_exists ? "Found" : "Missing / CSD down"} />
      </div>

      {blockers.length ? (
        <div className="mt-6 rounded-3xl border border-amber-500/20 bg-amber-500/10 p-5">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-amber-200">
            <ShieldCheck size={18} />
            Blockers
          </h3>
          <div className="mt-3 space-y-2">
            {blockers.map((item, index) => (
              <div key={index} className="rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-sm text-amber-100">
                <strong>{item.area}</strong>: {item.message}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          onClick={check}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw size={16} className={busy ? "animate-spin" : ""} />
          Run Go-Live Check
        </button>

        <button
          onClick={runOnce}
          disabled={busy || !ready}
          className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
        >
          <Play size={16} />
          Run Final Automation Once
        </button>

        <button
          onClick={refresh}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
        >
          <Rocket size={16} />
          Refresh Status
        </button>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <div>
          <div className="mb-2 text-sm font-medium text-slate-300">Status Snapshot</div>
          <pre className="max-h-80 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-300">
            {JSON.stringify(status || {}, null, 2)}
          </pre>
        </div>
        <div>
          <div className="mb-2 text-sm font-medium text-slate-300">Last Run</div>
          <pre className="max-h-80 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-300">
            {JSON.stringify(lastRun || {}, null, 2)}
          </pre>
        </div>
      </div>
    </section>
  );
}
