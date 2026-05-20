import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import SLAMetricsPanel from "../components/observability/SLAMetricsPanel.tsx";
import { useSLAMonitoring } from "../hooks/useSLAMonitoring";

export default function SLAMonitoringPage() {
  const sla = useSLAMonitoring();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={sla.stale ? "stale" : sla.refreshing ? "refreshing" : "ready"}
        dataSource={sla.dataSource}
        lastUpdated={sla.lastUpdated}
        loading={sla.loading}
        refreshing={sla.refreshing}
        error={sla.error}
      />
      <SLAMetricsPanel sla={sla.sla} loading={sla.loading} refreshing={sla.refreshing} stale={sla.stale} error={sla.error} onRetry={sla.refresh} />
      <div className="glass-card rounded-3xl p-5 text-sm text-slate-400">
        SLA monitoring is advisory only and does not change workflow control, proof capture, or submission behavior.
      </div>
    </div>
  );
}
