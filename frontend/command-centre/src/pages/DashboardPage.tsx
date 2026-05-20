import TopFilterBar from "../components/ui/TopFilterBar.tsx";
import MetricCard from "../components/dashboard/MetricCard.tsx";
import ProvinceHeatMap from "../components/heatmap/ProvinceHeatMap.tsx";
import OpportunityRadar from "../components/radar/OpportunityRadar.tsx";
import AnalyticsPanel from "../components/charts/AnalyticsPanel.tsx";
import GovernanceRulesGrid from "../components/governance/GovernanceRulesGrid.tsx";
import OperationalHealthPanel from "../components/health/OperationalHealthPanel.tsx";
import OperationalAlertsPanel from "../components/workflows/OperationalAlertsPanel.tsx";
import StartupValidationPanel from "../components/runtime/StartupValidationPanel.tsx";
import { useObservability } from "../hooks/useObservability";
import useTelemetryStore from "../store/telemetryStore";
import { BadgeDollarSign, FileText, Gauge, LineChart, PackageCheck, Percent } from "lucide-react";
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
  const observability = useObservability();
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
        <StartupValidationPanel />
      </div>
      <div className="mt-6 glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-black text-white">Observability Summary</h3>
            <p className="mt-1 text-sm text-slate-400">Prometheus, Grafana, SLA and runtime anomaly visibility for supervised-live operations.</p>
          </div>
          <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
            {observability.dataSource || "runtime_fallback"}
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Prometheus Metrics" value={observability.summary.prometheusMetricsCount || 0} subtitle="Metrics export coverage" icon={LineChart} accent="cyan" state={observability.stale ? "stale" : "ready"} />
          <MetricCard title="Grafana Dashboards" value={observability.summary.grafanaDashboards || 0} subtitle="Dashboard definitions" icon={Gauge} accent="green" state={observability.stale ? "stale" : "ready"} />
          <MetricCard title="SLA Breaches" value={observability.sla?.breachedMetrics?.length || 0} subtitle="Service-level warnings" icon={BadgeDollarSign} accent="amber" state={observability.stale ? "stale" : "ready"} />
          <MetricCard title="Runtime Anomalies" value={observability.summary.anomalyCount || 0} subtitle="Advisory anomaly signals" icon={Percent} accent="red" state={observability.stale ? "stale" : "ready"} />
        </div>
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
