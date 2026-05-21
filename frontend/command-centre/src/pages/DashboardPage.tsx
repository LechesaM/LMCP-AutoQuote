import TopFilterBar from "../components/ui/TopFilterBar.tsx";
import MetricCard from "../components/dashboard/MetricCard.tsx";
import ProvinceHeatMap from "../components/heatmap/ProvinceHeatMap.tsx";
import OpportunityRadar from "../components/radar/OpportunityRadar.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import OperationalHealthPanel from "../components/health/OperationalHealthPanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import StartupValidationPanel from "../components/runtime/StartupValidationPanel.tsx";
import useTelemetryStore from "../store/telemetryStore";
import { BadgeDollarSign, FileText, PackageCheck, Percent } from "lucide-react";
import { Link } from "react-router-dom";
import { commandCentreRoutes } from "../routes/commandCentreRoutes";

export default function DashboardPage() {
  const commandMetrics = useTelemetryStore((state) => state.commandMetrics);
  const dataSource = useTelemetryStore((state) => state.dataSource);
  const lastRefreshedAt = useTelemetryStore((state) => state.lastRefreshedAt);
  const stale = useTelemetryStore((state) => state.stale);
  const loading = useTelemetryStore((state) => state.loading);
  const refreshing = useTelemetryStore((state) => state.refreshing);
  const error = useTelemetryStore((state) => state.error);
  const telemetryLabel =
    dataSource === "runtime"
      ? "Live runtime telemetry"
      : dataSource === "mixed"
        ? "Mixed runtime / persistence telemetry"
        : dataSource === "persistence"
          ? "Persistence-backed telemetry"
          : "Fallback telemetry";
  const metricState = loading ? "loading" : refreshing || stale ? "stale" : "ready";

  return (
    <>
      <TopFilterBar />
      <div className="mt-4 rounded-3xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-xs font-semibold uppercase tracking-[.22em] text-slate-300">
        <div className="flex flex-wrap items-center gap-3">
          <span>{telemetryLabel}</span>
          <span className="text-slate-500">•</span>
          <span>Last updated {lastRefreshedAt || "unknown"}</span>
          <span className="text-slate-500">•</span>
          <span>{loading ? "Loading" : refreshing ? "Refreshing" : stale ? "Stale" : "Current"}</span>
          {error ? (
            <>
              <span className="text-slate-500">•</span>
              <span className="text-command-amber">Refresh error</span>
            </>
          ) : null}
        </div>
      </div>
      <div className="mt-6">
        <OperationalHealthPanel />
      </div>
      <div className="mt-6">
        <StartupValidationPanel />
      </div>
      <div className="mt-6">
        <OperationalAlertsPanel />
      </div>
      <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-4">
        <MetricCard title="Total Harvested RFQs" value={commandMetrics.totalHarvested} subtitle="Live runtime totals" icon={FileText} accent="cyan" state={metricState} />
        <MetricCard title="Eligible RFQs" value={commandMetrics.eligibleRfqs} subtitle="Supply & delivery qualified" icon={PackageCheck} state={metricState} />
        <MetricCard title="High Profit RFQs" value={commandMetrics.highProfitRfqs} subtitle="Above target threshold" icon={BadgeDollarSign} accent="amber" state={metricState} />
        <MetricCard title="Avg Margin" value={`${Number(commandMetrics.avgMargin || 0).toFixed(2)}%`} subtitle="Target minimum 25%" icon={Percent} state={metricState} />
      </section>
      <section className="mt-6 grid gap-6 2xl:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <ProvinceHeatMap />
          <OpportunityRadar />
        </div>
        <AnalyticsPanel />
      </section>
      <section className="mt-6 space-y-4">
        <div>
          <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Primary operator surface</div>
          <div className="mt-3 grid gap-4 md:grid-cols-3 xl:grid-cols-3">
            {commandCentreRoutes
              .filter((route) =>
                [
                  "/review",
                  "/operations",
                  "/pricing-evidence",
                  "/governance",
                  "/operator-assignments",
                  "/governance-compliance",
                ].includes(route.path),
              )
              .map((route) => (
                <Link key={route.path} to={route.path} className="glass-card rounded-3xl p-5 transition hover:scale-[1.01] hover:border-command-cyan/30">
                  <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Navigate</div>
                  <div className="mt-2 text-lg font-black text-white">{route.label}</div>
                  <div className="mt-1 text-sm text-slate-400">{route.description}</div>
                </Link>
              ))}
          </div>
        </div>
      </section>
    </>
  );
}
