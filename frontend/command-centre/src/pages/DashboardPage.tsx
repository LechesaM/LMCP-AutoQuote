import TopFilterBar from "../components/ui/TopFilterBar.tsx";
import MetricCard from "../components/dashboard/MetricCard.tsx";
import ProvinceHeatMap from "../components/heatmap/ProvinceHeatMap.tsx";
import OpportunityRadar from "../components/radar/OpportunityRadar.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import GovernanceRulesGrid from "../components/governance/GovernanceRulesGrid.tsx";
import OperationalHealthPanel from "../components/health/OperationalHealthPanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import useTelemetryStore from "../store/telemetryStore";
import { BadgeDollarSign, FileText, Gauge, LineChart, PackageCheck, Percent } from "lucide-react";
import { Link } from "react-router-dom";
import { commandCentreRoutes } from "../routes/commandCentreRoutes";

export default function DashboardPage() {
  const { commandMetrics, dataSource, lastRefreshedAt, stale, loading, refreshing, error } = useTelemetryStore((state) => ({
    commandMetrics: state.commandMetrics,
    dataSource: state.dataSource,
    lastRefreshedAt: state.lastRefreshedAt,
    stale: state.stale,
    loading: state.loading,
    refreshing: state.refreshing,
    error: state.error,
  }));
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
      <div className="mt-4 flex flex-wrap gap-3">
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {telemetryLabel}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Last updated {lastRefreshedAt || "unknown"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {loading ? "Loading" : refreshing ? "Refreshing" : stale ? "Stale" : "Current"}
        </div>
        {error ? (
          <div className="rounded-full border border-command-amber/40 bg-command-amber/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-command-amber">
            Refresh error
          </div>
        ) : null}
      </div>
      <div className="mt-6">
        <OperationalHealthPanel />
      </div>
      <div className="mt-6">
        <OperationalAlertsPanel />
      </div>
      <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-6">
        <MetricCard title="Total Harvested RFQs" value={commandMetrics.totalHarvested} subtitle="Live runtime totals" icon={FileText} accent="cyan" state={metricState} />
        <MetricCard title="Eligible RFQs" value={commandMetrics.eligibleRfqs} subtitle="Supply & delivery qualified" icon={PackageCheck} state={metricState} />
        <MetricCard
          title="Total Estimated Value"
          value={`R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(commandMetrics.estimatedValue || 0))}`}
          subtitle="Qualified province value"
          icon={LineChart}
          accent="cyan"
          state={metricState}
        />
        <MetricCard title="High Profit RFQs" value={commandMetrics.highProfitRfqs} subtitle="Above target threshold" icon={BadgeDollarSign} accent="amber" state={metricState} />
        <MetricCard
          title="Avg Estimated Profit"
          value={`R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(commandMetrics.avgEstimatedProfit || 0))}`}
          subtitle="Per eligible RFQ"
          icon={Gauge}
          state={metricState}
        />
        <MetricCard title="Avg Margin" value={`${Number(commandMetrics.avgMargin || 0).toFixed(2)}%`} subtitle="Target minimum 25%" icon={Percent} state={metricState} />
      </section>
      <section className="mt-6 grid gap-6 2xl:grid-cols-[1fr_420px]">
        <div className="space-y-6">
          <ProvinceHeatMap />
          <OpportunityRadar />
        </div>
        <AnalyticsPanel />
      </section>
      <section className="mt-6 grid gap-4 md:grid-cols-3 xl:grid-cols-5">
        {commandCentreRoutes
          .filter((route) => route.path !== "/dashboard" && route.path !== "/governance")
          .map((route) => (
            <Link key={route.path} to={route.path} className="glass-card rounded-3xl p-5 transition hover:scale-[1.01] hover:border-command-cyan/30">
              <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Navigate</div>
              <div className="mt-2 text-lg font-black text-white">{route.label}</div>
              <div className="mt-1 text-sm text-slate-400">{route.description}</div>
            </Link>
          ))}
      </section>
      <div className="mt-6">
        <GovernanceRulesGrid />
      </div>
    </>
  );
}
