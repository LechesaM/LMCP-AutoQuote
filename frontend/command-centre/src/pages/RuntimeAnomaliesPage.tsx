import OperationalStatusBanner from "../components/runtime/OperationalStatusBanner.tsx";
import RuntimeAnomalyPanel from "../components/observability/RuntimeAnomalyPanel.tsx";
import { Link } from "react-router-dom";
import { useRuntimeAnomalies } from "../hooks/useRuntimeAnomalies";

export default function RuntimeAnomaliesPage() {
  const anomalies = useRuntimeAnomalies();

  return (
    <div className="space-y-6">
      <OperationalStatusBanner
        state={anomalies.stale ? "stale" : anomalies.refreshing ? "refreshing" : "ready"}
        dataSource={anomalies.dataSource}
        lastUpdated={anomalies.lastUpdated}
        loading={anomalies.loading}
        refreshing={anomalies.refreshing}
        error={anomalies.error}
      />
      <div className="grid gap-3 md:grid-cols-3">
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Severity Trend</div>
          <div className="mt-2 text-3xl font-black text-white">{anomalies.anomalies.severityCounts?.critical || 0}</div>
          <div className="mt-1 text-sm text-slate-400">Critical advisory anomalies</div>
        </div>
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-amber">Incident Linkage</div>
          <div className="mt-2 text-sm text-slate-300">Anomaly context is reviewed through governed incident workflows.</div>
          <Link to="/incident-management" className="mt-3 inline-flex text-sm font-bold text-command-cyan">
            Open Incident Management
          </Link>
        </div>
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-green">Affected Systems</div>
          <div className="mt-2 text-sm text-slate-300">Queue, telemetry, source reliability and auth signals are monitored.</div>
        </div>
      </div>
      <RuntimeAnomalyPanel anomalies={anomalies.anomalies} loading={anomalies.loading} refreshing={anomalies.refreshing} stale={anomalies.stale} error={anomalies.error} onRetry={anomalies.refresh} />
      <div className="glass-card rounded-3xl p-5 text-sm text-slate-400">
        Anomaly detection remains advisory only. Incidents are still handled through governed operator workflows.
      </div>
    </div>
  );
}
