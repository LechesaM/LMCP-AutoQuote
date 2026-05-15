import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Globe,
  Layers3,
  RefreshCw,
  Server,
  Shield,
  TrendingUp,
  Zap,
  BarChart3,
} from "lucide-react";

const API_BASE =
  (typeof window !== "undefined" && (window as any).__LMCP_API_BASE__) ||
  import.meta?.env?.VITE_API_BASE ||
  "http://localhost:8000";

type EngineMode = "active" | "paused" | "emergency_stop";

declare global {
  interface Window {
    __LMCP_API_BASE__?: string;
  }
}

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

async function fetchJson(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function formatMoney(value: number | null | undefined) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("en-ZA").format(Number(value || 0));
}

function toneForStatus(value: string) {
  const v = String(value || "").toLowerCase();
  if (["ok", "healthy", "submitted", "active", "operational", "running"].includes(v)) return "text-emerald-300";
  if (["slow", "warning", "queued", "pending", "manual_action_required", "paused"].includes(v)) return "text-amber-300";
  if (["failed", "blocked", "error", "down", "emergency_stop", "stopped"].includes(v)) return "text-red-300";
  return "text-cyan-200";
}

function Panel({ title, right, children, className = "" }: { title: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className={cn(
        "rounded-2xl border border-cyan-400/15 bg-slate-950/75 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_40px_rgba(8,145,178,0.08)] backdrop-blur-sm",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-cyan-400/10 px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-100/85">{title}</h3>
        {right}
      </div>
      <div className="p-4">{children}</div>
    </motion.div>
  );
}

function StatCard({ label, value, sub, icon: Icon, tone }: { label: string; value: string; sub?: string; icon: any; tone: "cyan" | "green" | "amber" | "red" }) {
  const toneMap = {
    cyan: "text-cyan-300 border-cyan-400/15 bg-cyan-400/5",
    green: "text-emerald-300 border-emerald-400/15 bg-emerald-400/5",
    amber: "text-amber-300 border-amber-400/15 bg-amber-400/5",
    red: "text-red-300 border-red-400/15 bg-red-400/5",
  } as const;

  return (
    <div className={cn("rounded-2xl border p-4", toneMap[tone])}>
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</div>
        <Icon className="h-4 w-4" />
      </div>
      <div className="mt-3 flex items-end gap-2">
        <div className="text-4xl font-bold leading-none">{value}</div>
        {sub ? <div className="pb-1 text-sm font-medium">{sub}</div> : null}
      </div>
    </div>
  );
}

function MiniSparkline({ values, color = "stroke-cyan-400" }: { values: number[]; color?: string }) {
  const normalized = values.length ? values : [0, 0, 0, 0];
  const max = Math.max(...normalized, 1);
  const min = Math.min(...normalized, 0);
  const width = 240;
  const height = 70;
  const step = width / Math.max(normalized.length - 1, 1);
  const points = normalized
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / Math.max(max - min, 1)) * (height - 10) - 5;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-20 w-full">
      <defs>
        <linearGradient id="sparkFillLive" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(34,211,238,0.35)" />
          <stop offset="100%" stopColor="rgba(34,211,238,0.02)" />
        </linearGradient>
      </defs>
      <path d={`M 0 ${height} L ${points} L ${width} ${height} Z`} fill="url(#sparkFillLive)" />
      <polyline fill="none" strokeWidth="2.5" className={color} points={points} />
    </svg>
  );
}

function Gauge({ value, label }: { value: number; label: string }) {
  const safe = Math.max(0, Math.min(100, Number(value || 0)));
  const rotation = -110 + (safe / 100) * 220;
  return (
    <div className="relative mx-auto flex h-40 w-40 items-center justify-center rounded-full border border-cyan-400/10 bg-slate-900/70">
      <div className="absolute inset-3 rounded-full border border-cyan-500/10" />
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.14),transparent_58%)]" />
      <div className="absolute h-1 w-16 rounded-full bg-gradient-to-r from-amber-300 via-orange-400 to-red-500 shadow-[0_0_14px_rgba(251,146,60,0.55)]" style={{ transform: `rotate(${rotation}deg)`, transformOrigin: "50% 50%" }} />
      <div className="text-center">
        <div className="text-3xl font-bold text-cyan-100">{safe}%</div>
        <div className="mt-1 text-[11px] uppercase tracking-[0.22em] text-slate-400">{label}</div>
      </div>
    </div>
  );
}

function RadarPanel({ points }: { points: { x: number; y: number; tone: string }[] }) {
  return (
    <div className="relative aspect-square overflow-hidden rounded-2xl border border-cyan-400/10 bg-[radial-gradient(circle_at_center,rgba(74,222,128,0.15),transparent_30%),radial-gradient(circle_at_center,rgba(34,211,238,0.06),transparent_65%)]">
      {[20, 35, 50, 65, 80].map((r) => (
        <div key={r} className="absolute left-1/2 top-1/2 rounded-full border border-cyan-300/15" style={{ width: `${r}%`, height: `${r}%`, transform: "translate(-50%, -50%)" }} />
      ))}
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-cyan-300/15" />
      <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-cyan-300/15" />
      {[45, 90, 135].map((deg) => (
        <div key={deg} className="absolute left-1/2 top-1/2 h-[1px] w-[95%] origin-center bg-cyan-300/10" style={{ transform: `translate(-50%, -50%) rotate(${deg}deg)` }} />
      ))}
      <div className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-300 shadow-[0_0_16px_rgba(34,211,238,0.85)]" />
      {points.map((p, i) => (
        <div key={i} className={cn("absolute h-3 w-3 rounded-full shadow-[0_0_14px_rgba(255,255,255,0.35)]", p.tone)} style={{ left: `${p.x}%`, top: `${p.y}%` }} />
      ))}
    </div>
  );
}

function SouthAfricaHeatmap({ activeTenders }: { activeTenders: number }) {
  const clusters = [[548,138,32],[580,172,14],[650,255,28],[524,286,18],[408,265,26],[323,332,24],[244,372,28],[344,200,20],[458,364,20],[593,335,16],[293,255,14],[705,312,12]];
  return (
    <div className="relative h-full min-h-[360px] overflow-hidden rounded-2xl border border-cyan-400/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98)),radial-gradient(circle_at_50%_45%,rgba(249,115,22,0.16),transparent_45%)]">
      <div className="absolute inset-0 opacity-25 [background-image:linear-gradient(rgba(34,211,238,0.22)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.22)_1px,transparent_1px)] [background-size:38px_38px]" />
      <svg viewBox="0 0 900 520" className="absolute inset-0 h-full w-full">
        <defs>
          <filter id="glowLive">
            <feGaussianBlur stdDeviation="6" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <path d="M171 112 L282 88 L357 56 L488 44 L628 56 L721 102 L766 196 L752 300 L699 385 L604 445 L462 470 L356 454 L259 420 L198 366 L148 286 L126 202 Z" fill="rgba(10,20,35,0.72)" stroke="rgba(251,146,60,0.95)" strokeWidth="4" filter="url(#glowLive)" />
        {clusters.map(([x, y, r], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r={r * 1.9} fill="rgba(249,115,22,0.10)" />
            <circle cx={x} cy={y} r={r} fill="rgba(251,146,60,0.9)" filter="url(#glowLive)" />
            <circle cx={x} cy={y} r={r * 0.45} fill="rgba(255,241,118,0.95)" />
          </g>
        ))}
      </svg>
      <div className="absolute right-4 top-4 rounded-xl border border-cyan-400/15 bg-slate-950/70 px-4 py-3 text-xs text-slate-300 backdrop-blur">
        <div className="mb-2 text-[11px] uppercase tracking-[0.24em] text-cyan-200">Tender Heatmap</div>
        <div className="space-y-2">
          <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Hot</div>
          <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-orange-400" /> Moderate</div>
          <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-yellow-300" /> Low Activity</div>
        </div>
        <div className="mt-4 space-y-1 border-t border-cyan-400/10 pt-3 text-slate-200">
          <div>Active Tenders: <span className="font-semibold text-orange-300">{formatNumber(activeTenders)}</span></div>
          <div>Regions Monitored: <span className="font-semibold text-cyan-300">9 Provinces</span></div>
        </div>
      </div>
    </div>
  );
}

function ArchitecturePanel() {
  const nodes = [
    { x: 12, y: 16, label: "API" },
    { x: 12, y: 40, label: "Scheduler" },
    { x: 12, y: 70, label: "DB" },
    { x: 42, y: 16, label: "Harvesters" },
    { x: 42, y: 40, label: "Task Queue", hot: true },
    { x: 42, y: 62, label: "AI Scoring" },
    { x: 42, y: 84, label: "Pipeline" },
    { x: 42, y: 95, label: "Monitoring" },
    { x: 76, y: 12, label: "Artifacts" },
    { x: 76, y: 42, label: "Quote Packs", hot: true },
    { x: 76, y: 78, label: "History" },
  ];
  return (
    <div className="relative min-h-[320px] rounded-2xl border border-cyan-400/10 bg-slate-950/80 p-4">
      {nodes.map((node, i) => (
        <div
          key={i}
          className={cn(
            "absolute flex h-12 items-center justify-center rounded-xl border px-3 text-xs font-semibold tracking-[0.12em] text-slate-100 shadow-[0_0_18px_rgba(8,145,178,0.08)]",
            node.hot ? "border-orange-400/30 bg-gradient-to-r from-orange-600/70 to-amber-500/60" : "border-cyan-400/15 bg-slate-900/90",
          )}
          style={{ left: `${node.x}%`, top: `${node.y}%`, width: node.label.length > 10 ? 150 : 110, transform: "translate(-50%, -50%)" }}
        >
          {node.label}
        </div>
      ))}
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {[[20,16,34,16],[20,40,34,40],[20,70,34,84],[50,16,68,12],[50,40,68,42],[50,62,68,42],[50,84,68,78],[50,40,50,62],[50,62,50,84],[20,16,20,40]].map((line, i) => (
          <line key={i} x1={line[0]} y1={line[1]} x2={line[2]} y2={line[3]} stroke="rgba(103,232,249,0.38)" strokeWidth="0.55" />
        ))}
      </svg>
    </div>
  );
}

function useLmcpData() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [engineBusy, setEngineBusy] = useState(false);
  const [engineMode, setEngineMode] = useState<EngineMode>("paused");
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [dashboardSummary, setDashboardSummary] = useState<any>(null);
  const [profit, setProfit] = useState<any>(null);
  const [submissionHistory, setSubmissionHistory] = useState<any>(null);
  const [opportunities, setOpportunities] = useState<any[]>([]);

  const load = async (silent = false) => {
    try {
      if (silent) setRefreshing(true); else setLoading(true);
      setError(null);

      const [healthRes, summaryRes, profitRes, historyRes, opportunitiesRes, autonomousRes] = await Promise.allSettled([
        fetchJson("/system/health"),
        fetchJson("/dashboard/summary"),
        fetchJson("/submission-analytics/profit"),
        fetchJson("/submission-history?limit=12"),
        fetchJson("/opportunities?limit=24"),
        fetchJson("/autonomous/status"),
      ]);

      if (healthRes.status === "fulfilled") setSystemHealth(healthRes.value);
      if (summaryRes.status === "fulfilled") setDashboardSummary(summaryRes.value);
      if (profitRes.status === "fulfilled") setProfit(profitRes.value);
      if (historyRes.status === "fulfilled") setSubmissionHistory(historyRes.value);
      if (opportunitiesRes.status === "fulfilled") {
        const rows = Array.isArray(opportunitiesRes.value) ? opportunitiesRes.value : opportunitiesRes.value?.items || opportunitiesRes.value?.results || [];
        setOpportunities(Array.isArray(rows) ? rows : []);
      }
      if (autonomousRes.status === "fulfilled") {
        const apiMode = String(autonomousRes.value?.engine_state || autonomousRes.value?.status || autonomousRes.value?.mode || "paused").toLowerCase();
        if (apiMode.includes("emergency")) setEngineMode("emergency_stop");
        else if (apiMode.includes("active") || apiMode.includes("running") || apiMode.includes("on")) setEngineMode("active");
        else setEngineMode("paused");
      }

      const allFailed = [healthRes, summaryRes, profitRes, historyRes, opportunitiesRes].every((r) => r.status === "rejected");
      if (allFailed) setError("Unable to reach LMCP backend. Confirm the API is running and CORS is allowed.");
    } catch (err: any) {
      setError(err?.message || "Failed to load data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(() => load(true), 15000);
    return () => window.clearInterval(id);
  }, []);

  const setAutonomousMode = async (mode: EngineMode) => {
    setEngineBusy(true);
    try {
      const endpoint = mode === "active" ? "/autonomous/start" : mode === "emergency_stop" ? "/autonomous/emergency-stop" : "/autonomous/pause";
      try {
        await fetchJson(endpoint, { method: "POST" });
      } catch {
        if (mode === "active") await fetchJson("/autonomous/run-once", { method: "POST" }).catch(() => null);
      }
      setEngineMode(mode);
      await load(true);
    } finally {
      setEngineBusy(false);
    }
  };

  return { loading, error, refreshing, engineBusy, engineMode, systemHealth, dashboardSummary, profit, submissionHistory, opportunities, setAutonomousMode, reload: () => load(true) };
}

export default function LMCPLiveMissionControl() {
  const { loading, error, refreshing, engineBusy, engineMode, systemHealth, dashboardSummary, profit, submissionHistory, opportunities, setAutonomousMode, reload } = useLmcpData();

  const recentSubmissions = dashboardSummary?.recent_submissions || submissionHistory?.items || [];
  const successTracking = dashboardSummary?.submission_success_tracking || {};
  const fileSummary = dashboardSummary?.summary || {};
  const activePortals = dashboardSummary?.portal_radar?.total_portals || systemHealth?.portal_radar?.total_portals || 0;
  const healthyPortals = dashboardSummary?.portal_radar?.healthy || systemHealth?.portal_radar?.healthy || 0;
  const slowPortals = dashboardSummary?.portal_radar?.slow || systemHealth?.portal_radar?.slow || 0;
  const blockedPortals = dashboardSummary?.portal_radar?.blocked || systemHealth?.portal_radar?.blocked || 0;
  const submitted = successTracking?.submitted || dashboardSummary?.submission_history?.submitted || 0;
  const failed = successTracking?.failed || dashboardSummary?.submission_history?.failed || 0;
  const totalHistory = successTracking?.total || dashboardSummary?.submission_history?.total || 0;
  const systemLoad = totalHistory > 0 ? Math.round((submitted / Math.max(totalHistory, 1)) * 100) : 0;

  const opportunityBuckets = useMemo(() => {
    const rows = opportunities.map((row: any, index: number) => ({
      title: row?.title || row?.description || row?.buyer_rfq_number || `Opportunity ${index + 1}`,
      buyer: row?.buyer_name || row?.organ_of_state || row?.department || "Unknown buyer",
      value: Number(row?.estimated_value || row?.estimated_revenue || row?.value || row?.amount || 0),
      score: Number(row?.opportunity_score || row?.score || row?.priority_score || 0),
      channel: row?.submission_method || (row?.recipient_email ? "email" : row?.portal_url ? "portal" : "unknown"),
    }));
    const sorted = [...rows].sort((a, b) => b.score - a.score);
    return {
      hot: sorted.filter((r) => r.score >= 80).slice(0, 4),
      medium: sorted.filter((r) => r.score >= 40 && r.score < 80).slice(0, 4),
      low: sorted.filter((r) => r.score < 40).slice(0, 4),
    };
  }, [opportunities]);

  const historyByDay = Array.isArray(profit?.by_day) ? profit.by_day : [];
  const sparkValues = historyByDay.length ? historyByDay.map((d: any) => Number(d.estimated_profit || 0)) : [0, 1, 0, 2];
  const retryVsFail = [Number(submitted || 0), Number(failed || 0), Number(profit?.counted_records || 0), Number(profit?.uncosted_records || 0)];
  const radarPoints = useMemo(() => {
    const src = opportunities.length ? opportunities.slice(0, 10) : new Array(9).fill(null);
    return src.map((row: any, i: number) => {
      const score = Number(row?.opportunity_score || row?.score || (i + 1) * 9 || 0);
      const x = 16 + ((score * 7 + i * 11) % 68);
      const y = 14 + ((score * 5 + i * 13) % 72);
      const tone = score >= 80 ? "bg-red-400" : score >= 50 ? "bg-yellow-300" : "bg-green-400";
      return { x, y, tone };
    });
  }, [opportunities]);

  const cards = [
    { label: "Active Portals", value: formatNumber(activePortals), sub: "Live", icon: Globe, tone: "cyan" as const },
    { label: "Healthy", value: formatNumber(healthyPortals), sub: "Portals", icon: CheckCircle2, tone: "green" as const },
    { label: "Slow", value: formatNumber(slowPortals), sub: "Needs watch", icon: Activity, tone: "amber" as const },
    { label: "Blocked", value: formatNumber(blockedPortals), sub: "Attention", icon: AlertTriangle, tone: "red" as const },
  ];

  if (loading) {
    return <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center"><div className="text-center"><div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" /><div className="text-lg font-semibold text-cyan-200">Loading LMCP Mission Control...</div><div className="mt-2 text-sm text-slate-400">Connecting to {API_BASE}</div></div></div>;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.08),transparent_30%),linear-gradient(180deg,#020617_0%,#071120_45%,#020617_100%)] text-slate-100">
      <div className="mx-auto max-w-[1800px] p-4 md:p-6 xl:p-8">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 rounded-[28px] border border-cyan-400/15 bg-slate-950/75 px-5 py-4 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_50px_rgba(14,165,233,0.06)] backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-3"><div className="rounded-2xl border border-cyan-400/15 bg-cyan-500/10 p-2 text-cyan-300"><Shield className="h-6 w-6" /></div><div><div className="text-2xl font-bold tracking-[0.2em] text-cyan-100">LMCP</div><div className="text-xs uppercase tracking-[0.28em] text-slate-400">Live Mission Control</div></div></div>
              <div className="mt-3 text-xs text-slate-400">Backend: {API_BASE}</div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-xl border border-cyan-400/15 bg-slate-900/80 px-3 py-2 text-sm"><span className="text-slate-400">System: </span><span className={cn("font-semibold", toneForStatus(systemHealth?.status || "ok"))}>{systemHealth?.status || "unknown"}</span></div>
              <div className="rounded-xl border border-cyan-400/15 bg-slate-900/80 px-3 py-2 text-sm"><span className="text-slate-400">Engine Mode: </span><span className={cn("font-semibold uppercase", toneForStatus(engineMode))}>{engineMode.replace("_", " ")}</span></div>
              <div className="rounded-xl border border-cyan-400/15 bg-slate-900/80 px-3 py-2 text-sm"><span className="text-slate-400">Profit Records: </span><span className="font-semibold text-cyan-200">{formatNumber(profit?.counted_records || 0)}</span></div>
              <button onClick={reload} className="inline-flex items-center gap-2 rounded-xl border border-cyan-400/15 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20"><RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />Refresh</button>
              <button onClick={() => setAutonomousMode("active")} disabled={engineBusy} className={cn("inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition", engineMode === "active" ? "border-emerald-400/30 bg-emerald-500/20 text-emerald-200" : "border-emerald-400/20 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20", engineBusy && "opacity-60")}><Zap className="h-4 w-4" />ACTIVE</button>
              <button onClick={() => setAutonomousMode("paused")} disabled={engineBusy} className={cn("inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition", engineMode === "paused" ? "border-amber-400/30 bg-amber-500/20 text-amber-200" : "border-amber-400/20 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20", engineBusy && "opacity-60")}><Activity className="h-4 w-4" />PAUSED</button>
              <button onClick={() => setAutonomousMode("emergency_stop")} disabled={engineBusy} className={cn("inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition", engineMode === "emergency_stop" ? "border-red-400/30 bg-red-500/20 text-red-200" : "border-red-400/20 bg-red-500/10 text-red-200 hover:bg-red-500/20", engineBusy && "opacity-60")}><AlertTriangle className="h-4 w-4" />EMERGENCY STOP</button>
            </div>
          </div>
          {error ? <div className="mt-4 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div> : null}
        </motion.div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_1fr]">
          <div className="space-y-6">
            <Panel title="Portal Operations Overview" right={<div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Realtime</div>}>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">{cards.map((item) => <StatCard key={item.label} {...item} />)}</div>
              <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.15fr_1fr]">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-cyan-400/10 bg-slate-900/70 p-4"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">RFQ Folders</div><div className="mt-4 text-4xl font-bold text-cyan-50">{formatNumber(fileSummary?.rfq_folders || 0)}</div><div className="mt-2 text-sm text-slate-400">Harvested pack folders</div></div>
                  <div className="rounded-2xl border border-cyan-400/10 bg-slate-900/70 p-4"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Quote PDFs</div><div className="mt-4 text-4xl font-bold text-cyan-50">{formatNumber(fileSummary?.quote_pdfs || 0)}</div><div className="mt-2 text-sm text-slate-400">Generated quotations</div></div>
                  <div className="rounded-2xl border border-cyan-400/10 bg-slate-900/70 p-4"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Supplier Quotes</div><div className="mt-4 text-4xl font-bold text-cyan-50">{formatNumber(fileSummary?.supplier_quotes_found || 0)}</div><div className="mt-2 text-sm text-slate-400">Found in system</div></div>
                </div>
                <div className="rounded-2xl border border-cyan-400/10 bg-slate-900/70 p-4"><div className="mb-3 flex items-center justify-between"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Profit Trend</div><TrendingUp className="h-4 w-4 text-orange-300" /></div><MiniSparkline values={sparkValues} color="stroke-orange-400" /></div>
              </div>
            </Panel>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_0.9fr_0.9fr]">
              <Panel title="Submission Velocity" className="min-h-[240px]"><div className="mb-4 text-sm text-slate-400">Submitted: {formatNumber(submitted)} | Failed: {formatNumber(failed)}</div><MiniSparkline values={historyByDay.map((d: any) => Number(d.count || 0))} color="stroke-emerald-400" /><MiniSparkline values={retryVsFail} color="stroke-orange-400" /></Panel>
              <Panel title="System Load" className="min-h-[240px]"><Gauge value={systemLoad} label="Success Rate" /></Panel>
              <Panel title="Profit Snapshot" className="min-h-[240px]"><div className="space-y-3"><div><div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Revenue</div><div className="mt-1 text-xl font-bold text-cyan-100">{formatMoney(profit?.estimated_revenue)}</div></div><div><div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Cost</div><div className="mt-1 text-xl font-bold text-orange-300">{formatMoney(profit?.estimated_cost)}</div></div><div><div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Profit</div><div className="mt-1 text-2xl font-bold text-emerald-300">{formatMoney(profit?.estimated_profit)}</div></div></div></Panel>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <Panel title="Recent Submissions"><div className="space-y-3">{recentSubmissions.slice(0, 6).map((item: any, idx: number) => <div key={idx} className="flex items-center justify-between rounded-xl border border-cyan-400/10 bg-slate-900/80 px-3 py-3"><div><div className="text-sm font-semibold text-slate-100">{item?.buyer_rfq_number || item?.title || "Unnamed submission"}</div><div className="mt-1 text-xs text-slate-400">{item?.buyer_name || item?.recipient_email || item?.submission_method || "—"}</div></div><div className={cn("text-xs font-semibold uppercase tracking-[0.18em]", toneForStatus(item?.status))}>{item?.status || "unknown"}</div></div>)}</div></Panel>
              <Panel title="Profit Tracking Status"><div className="space-y-4">{[["Counted Records", formatNumber(profit?.counted_records || 0), "text-emerald-300"],["Uncosted Records", formatNumber(profit?.uncosted_records || 0), profit?.uncosted_records ? "text-amber-300" : "text-cyan-300"],["Submitted", formatNumber(submitted), "text-cyan-300"]].map(([name, value, tone]) => <div key={String(name)} className="flex items-center justify-between rounded-xl border border-cyan-400/10 bg-slate-900/80 px-3 py-3"><span className="text-slate-300">{name}</span><span className={cn("text-lg font-bold", String(tone))}>{value}</span></div>)}</div></Panel>
            </div>
          </div>

          <div className="space-y-6">
            <Panel title="South Africa Tender Heatmap" className="min-h-[470px]"><SouthAfricaHeatmap activeTenders={opportunities.length || fileSummary?.rfq_folders || 0} /></Panel>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <Panel title="Opportunity Radar"><RadarPanel points={radarPoints} /></Panel>
              <Panel title="Tender Priority Board">
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                  {[{ key: "hot", title: "Hot Tenders", tone: "from-red-600 to-orange-500" },{ key: "medium", title: "Medium Tenders", tone: "from-orange-500 to-amber-400" },{ key: "low", title: "Low Potential", tone: "from-slate-700 to-slate-500" }].map((section: any) => (
                    <div key={section.key} className="overflow-hidden rounded-2xl border border-cyan-400/10 bg-slate-950/70"><div className={cn("bg-gradient-to-r px-4 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-white", section.tone)}>{section.title}</div><div className="space-y-3 p-4">{(opportunityBuckets as any)[section.key].length ? (opportunityBuckets as any)[section.key].map((item: any, i: number) => <div key={i} className="rounded-xl border border-cyan-400/10 bg-slate-900/75 p-3"><div className="flex items-start justify-between gap-3"><div><div className="text-sm font-semibold text-slate-100">{item.title}</div><div className="mt-1 text-xs text-slate-400">{item.buyer}</div></div><div className="rounded-lg border border-cyan-400/10 bg-slate-950/80 px-2.5 py-1 text-sm font-bold text-emerald-300">{Math.round(item.score || 0)}</div></div><div className="mt-3 text-sm text-orange-300">Value: {item.value > 0 ? formatMoney(item.value) : "Unknown"}</div><div className="mt-3 inline-flex rounded-lg border border-cyan-400/10 bg-slate-950/80 px-2.5 py-1 text-[11px] uppercase tracking-[0.18em] text-cyan-200">{String(item.channel || "unknown")}</div></div>) : <div className="text-sm text-slate-400">No items loaded.</div>}</div></div>
                  ))}
                </div>
              </Panel>
            </div>
            <Panel title="Architecture & Control Mesh" right={<div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Live Flow</div>}><ArchitecturePanel /></Panel>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-5">
          {[{ label: "API Health", value: systemHealth?.status || "unknown", icon: Server },{ label: "Task Queue", value: "Live", icon: Layers3 },{ label: "AI Scoring", value: opportunities.length ? "Active" : "Idle", icon: Zap },{ label: "Monitoring", value: dashboardSummary?.submission_history?.available !== false ? "Backed Up" : "Limited", icon: Database },{ label: "Autonomous", value: engineMode === "active" ? "Running" : engineMode === "emergency_stop" ? "Stopped" : "Paused", icon: BarChart3 }].map((item) => {
            const Icon = item.icon;
            return <div key={item.label} className="rounded-2xl border border-cyan-400/10 bg-slate-950/70 px-4 py-3"><div className="flex items-center gap-3"><div className="rounded-xl border border-cyan-400/15 bg-cyan-400/10 p-2 text-cyan-300"><Icon className="h-4 w-4" /></div><div><div className="text-xs uppercase tracking-[0.2em] text-slate-400">{item.label}</div><div className={cn("mt-1 text-sm font-semibold", toneForStatus(item.value))}>{item.value}</div></div></div></div>;
          })}
        </div>
      </div>
    </div>
  );
}

