import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import AlertRoutingPanel from "../components/observability/AlertRoutingPanel.tsx";
import GrafanaStatusPanel from "../components/observability/GrafanaStatusPanel.tsx";
import LogAggregationPanel from "../components/observability/LogAggregationPanel.tsx";
import PrometheusHealthPanel from "../components/observability/PrometheusHealthPanel.tsx";
import RuntimePerformancePanel from "../components/observability/RuntimePerformancePanel.tsx";
import SentryIncidentPanel from "../components/observability/SentryIncidentPanel.tsx";
import UptimeMonitorPanel from "../components/observability/UptimeMonitorPanel.tsx";
import { useObservability } from "../hooks/useObservability";

export default function ObservabilityPage() {
  const observability = useObservability();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={observability.stale ? "stale" : observability.refreshing ? "refreshing" : "ready"}
        dataSource={observability.dataSource}
        lastUpdated={observability.lastUpdated}
        loading={observability.loading}
        refreshing={observability.refreshing}
        error={observability.error}
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <PrometheusHealthPanel prometheus={observability.prometheus} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
        <GrafanaStatusPanel grafana={observability.grafana} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <SentryIncidentPanel sentry={observability.sentry} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
        <UptimeMonitorPanel uptime={observability.uptime} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
      </div>
      <AlertRoutingPanel alerts={observability.alerts} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
      <LogAggregationPanel logs={observability.logs} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
      <RuntimePerformancePanel performance={observability.performance} loading={observability.loading} refreshing={observability.refreshing} stale={observability.stale} error={observability.error} onRetry={observability.refresh} />
    </div>
  );
}
