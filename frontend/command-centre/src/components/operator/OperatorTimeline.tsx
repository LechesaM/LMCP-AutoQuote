import DataTable from "../ui/DataTable.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { useOperatorTimeline } from "../../hooks/useOperatorTimeline";

export default function OperatorTimeline({ onSelectEvent, snapshot = null }) {
  const live = useOperatorTimeline();
  const { events, loading, refreshing, error, dataSource, generatedAt, refresh } = snapshot || live;

  return (
    <SectionPanel
      title="Activity Timeline"
      description="Append-only operator actions, alerts, queue changes and governance acknowledgements."
      state={loading ? "loading" : error ? "error" : refreshing ? "refreshing" : dataSource !== "runtime" ? "stale" : "ready"}
      actions={
        <div className="flex items-center gap-2">
          <StateBadge state={dataSource === "runtime" ? "ready" : "stale"} />
          <button className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300" onClick={refresh} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300">
          Data source {dataSource || "runtime_fallback"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300">
          Last updated {generatedAt || "unknown"}
        </div>
      </div>
      <DataTable
        columns={[
          { key: "eventType", header: "Event", sortable: true, render: (row) => row.eventType, sortValue: (row) => row.eventType },
          { key: "title", header: "Title", sortable: true, render: (row) => <div className="font-bold text-white">{row.title}</div>, sortValue: (row) => row.title },
          { key: "operatorId", header: "Operator", sortable: true, render: (row) => row.operatorId || "—", sortValue: (row) => row.operatorId || "" },
          { key: "tenderId", header: "RFQ", sortable: true, render: (row) => row.tenderId || "—", sortValue: (row) => row.tenderId || "" },
          { key: "severity", header: "Severity", sortable: true, render: (row) => row.severity, sortValue: (row) => row.severity },
          { key: "createdAt", header: "Created", sortable: true, render: (row) => row.createdAt, sortValue: (row) => row.createdAt },
        ]}
        defaultSortKey="createdAt"
        emptyMessage="No operator activity events available."
        loading={loading}
        onRowClick={(row) => onSelectEvent?.(row)}
        onRetry={refresh}
        pageSize={10}
        rowKey={(row) => row.eventId}
        rows={events}
        searchAccessor={(row) => `${row.eventType} ${row.title} ${row.operatorId} ${row.tenderId} ${row.severity}`}
        searchPlaceholder="Search timeline"
        stale={dataSource !== "runtime"}
        title="Operator Activity"
      />
    </SectionPanel>
  );
}
