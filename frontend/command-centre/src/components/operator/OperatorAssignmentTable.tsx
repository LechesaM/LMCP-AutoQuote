import DataTable from "../ui/DataTable.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { useOperatorAssignments } from "../../hooks/useOperatorAssignments";

export default function OperatorAssignmentTable({ onSelectAssignment, selectedTenderId = "", snapshot = null }) {
  const live = useOperatorAssignments();
  const { assignments, recommendations, summary, capacity, loading, refreshing, error, dataSource, generatedAt, refresh } = snapshot || live;
  const selectedSummary = selectedTenderId ? `Selected ${selectedTenderId}` : "No assignment selected";

  return (
    <SectionPanel
      title="Operator Assignments"
      description="Assignment queues, ownership, workload and escalation recommendations are advisory only."
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
      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Assigned Today" value={summary.activeAssignments} tone="cyan" />
        <TelemetryStat label="Operators" value={summary.operators} tone="green" />
        <TelemetryStat label="Capacity" value={summary.capacity} tone="amber" />
        <TelemetryStat label="Remaining" value={capacity.remainingCapacity} tone={capacity.remainingCapacity < 200 ? "amber" : "green"} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Data source {dataSource || "runtime_fallback"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Last updated {generatedAt || "unknown"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Recommendations {recommendations.length}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {selectedSummary}
        </div>
      </div>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "tenderId", header: "RFQ ID", sortable: true, render: (row) => <div className="font-bold text-white">{row.tenderId}</div>, sortValue: (row) => row.tenderId, className: "min-w-[120px]" },
            { key: "operatorId", header: "Operator", sortable: true, render: (row) => row.operatorId, sortValue: (row) => row.operatorId },
            { key: "status", header: "Status", sortable: true, render: (row) => row.status, sortValue: (row) => row.status },
            { key: "priority", header: "Priority", sortable: true, render: (row) => row.priority, sortValue: (row) => row.priority },
            { key: "recommendation", header: "Recommendation", sortable: true, render: (row) => row.recommendation, sortValue: (row) => row.recommendation },
            { key: "workload", header: "Workload", sortable: true, render: (row) => row.workload, sortValue: (row) => row.workload },
            { key: "dueAt", header: "Due At", sortable: true, render: (row) => row.dueAt || "—", sortValue: (row) => row.dueAt || "" },
            { key: "source", header: "Source", sortable: true, render: (row) => row.source, sortValue: (row) => row.source },
            { key: "details", header: "Details", sortable: false, render: (row) => <div className="max-w-[280px] text-xs text-slate-400">{JSON.stringify(row.details)}</div> },
          ]}
          defaultSortKey="priority"
          description="Capacity is governed at 10 operators × 100/day = 1,000 total daily review capacity."
          emptyMessage="No operator assignments available."
          loading={loading}
          onRowClick={(row) => onSelectAssignment?.(row)}
          onRetry={refresh}
          pageSize={8}
          rowKey={(row) => row.assignmentId}
          rows={assignments}
          searchAccessor={(row) => `${row.tenderId} ${row.operatorId} ${row.status} ${row.recommendation} ${row.source}`}
          searchPlaceholder="Search assignments"
          stale={dataSource !== "runtime"}
          title="Operator Assignments"
        />
      </div>
    </SectionPanel>
  );
}
