import { AlertTriangle } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import DataTable from "../ui/DataTable.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function RuntimeAnomalyPanel({ anomalies = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const rows = anomalies.anomalies || [];
  if (loading) {
    return (
      <SectionPanel title="Runtime Anomalies" description="Advisory anomaly detection for runtime degradation." state="loading">
        <SkeletonCard lines={5} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Runtime Anomalies"
      description="Queue spikes, parser failures, stale telemetry and source reliability anomalies."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {anomalies.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      {rows.length ? (
        <DataTable
          title="Detected anomalies"
          description="Advisory-only anomaly records."
          rows={rows}
          columns={[
            { key: "type", header: "Type", render: (row) => row.type, sortable: true, sortValue: (row) => row.type },
            { key: "severity", header: "Severity", render: (row) => row.severity, sortable: true, sortValue: (row) => row.severity },
            { key: "message", header: "Message", render: (row) => row.message, sortable: true, sortValue: (row) => row.message },
            {
              key: "affectedSystems",
              header: "Affected Systems",
              render: (row) => (row.affectedSystems || []).join(", "),
              sortable: false,
            },
          ]}
          rowKey={(row) => row.anomalyId}
          searchPlaceholder="Search anomalies"
          searchAccessor={(row) => `${row.type} ${row.message} ${(row.affectedSystems || []).join(" ")}`}
          pageSize={5}
          emptyMessage="No runtime anomalies detected."
        />
      ) : (
        <EmptyTelemetryState title="No anomalies detected" description="The anomaly detector has not identified any advisory issues." />
      )}
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Anomaly Count</div>
          <div className="mt-2 text-3xl font-black text-white">{anomalies.anomalyCount || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Critical</div>
          <div className="mt-2 text-3xl font-black text-white">{anomalies.severityCounts?.critical || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.24em] text-slate-400">
            <AlertTriangle size={13} className="text-command-amber" /> Advisory Only
          </div>
          <div className="mt-2 text-slate-400">Anomalies never trigger autonomous remediation.</div>
        </div>
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
