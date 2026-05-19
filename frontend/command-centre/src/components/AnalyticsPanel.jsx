import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bell, Flame } from "lucide-react";
import { opportunityBreakdown, provinceDistribution, recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";
import StateBadge from "./ui/StateBadge.tsx";
import { SkeletonCard } from "./ui/SkeletonBlocks.tsx";
import ErrorBoundary from "./error/ErrorBoundary.tsx";
import ChartFallback from "./error/ChartFallback.tsx";

const colors = ["#22c55e", "#f59e0b", "#64748b"];

export default function AnalyticsPanel({ state = "ready", onRetry }) {
  if (state === "loading") {
    return (
      <div className="space-y-5">
        <div className="glass-card rounded-3xl p-5">
          <SkeletonCard lines={4} />
        </div>
        <div className="glass-card rounded-3xl p-5">
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="glass-card rounded-3xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-black text-white">Analytics</h3>
            <p className="text-sm text-slate-400">Unable to load chart telemetry.</p>
          </div>
          <StateBadge state="error" />
        </div>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const bars = state === "empty" ? [] : provinceDistribution.map((row) => ({ name: row.code, value: row.value }));
  const opportunities = state === "empty" ? [] : opportunityBreakdown;
  const alerts = state === "empty" ? [] : recentAlerts;
  const highs = state === "empty" ? [] : topHighProfitRfqs;

  return (
    <div className={`space-y-5 ${state === "stale" ? "opacity-85" : ""}`}>
      <div className="glass-card rounded-3xl p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-black text-white">Opportunity Breakdown</h3>
          <StateBadge state={state === "refreshing" ? "refreshing" : state === "stale" ? "stale" : "ready"} />
        </div>
        <div className="mt-4 h-[205px]">
          <ErrorBoundary fallback={ChartFallback}>
            {opportunities.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={opportunities} innerRadius={56} outerRadius={82} paddingAngle={4} dataKey="value">
                    {opportunities.map((entry, index) => (
                      <Cell key={entry.name} fill={colors[index]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(148,163,184,.25)", borderRadius: 14 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-700/60 bg-slate-950/35 text-sm text-slate-500">
                No opportunity data available.
              </div>
            )}
          </ErrorBoundary>
        </div>
        {opportunities.map((row, index) => (
          <div key={row.name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-300">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: colors[index] }} />
              {row.name}
            </span>
            <span className="font-black text-white">{row.value}</span>
          </div>
        ))}
      </div>

      <div className="glass-card rounded-3xl p-5">
        <h3 className="text-lg font-black text-white">Estimated Value by Province</h3>
        <div className="mt-4 h-[220px]">
          <ErrorBoundary fallback={ChartFallback}>
            {bars.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bars}>
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis hide />
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(148,163,184,.25)", borderRadius: 14 }} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} fill="#22c55e" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-700/60 bg-slate-950/35 text-sm text-slate-500">
                No chart data available.
              </div>
            )}
          </ErrorBoundary>
        </div>
      </div>

      <div className="glass-card rounded-3xl p-5">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-black text-white">
          <Flame size={19} className="text-command-amber" />
          Top High Profit RFQs
        </h3>
        <div className="space-y-3">
          {highs.length ? (
            highs.map((row) => (
              <div key={row.title} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
                <div className="text-sm font-bold text-white">{row.title}</div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-slate-400">{row.province}</span>
                  <span className="text-command-cyan">{row.value}</span>
                  <span className="font-bold text-command-green">{row.profit}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-700/60 bg-slate-950/35 p-4 text-sm text-slate-500">
              No high-profit RFQs available.
            </div>
          )}
        </div>
      </div>

      <div className="glass-card rounded-3xl p-5">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-black text-white">
          <Bell size={19} className="text-command-cyan" />
          Recent Alerts
        </h3>
        {alerts.length ? (
          alerts.map((alert) => (
            <div key={alert} className="mb-2 rounded-2xl border border-slate-700/50 bg-slate-950/40 px-3 py-2 text-sm text-slate-300">
              {alert}
            </div>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-700/60 bg-slate-950/35 p-4 text-sm text-slate-500">
            No alerts at the moment.
          </div>
        )}
      </div>
    </div>
  );
}
