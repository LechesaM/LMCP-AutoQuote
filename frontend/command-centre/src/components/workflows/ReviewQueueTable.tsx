import { useMemo, useState } from "react";
import { useReviewQueue } from "../../hooks/useReviewQueue";
import { formatCurrency } from "../../utils/formatters";
import DataTable from "../ui/DataTable.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";

export default function ReviewQueueTable() {
  const { items, summary } = useReviewQueue();
  const [onlyManual, setOnlyManual] = useState(false);

  const filteredItems = useMemo(() => (onlyManual ? items.filter((item) => item.recommendation !== "GO") : items), [items, onlyManual]);

  return (
    <SectionPanel
      title="Review Queue"
      description="Operator capacity and queue health remain advisory and manual-governed."
      actions={
        <button
          className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] ${onlyManual ? "border-command-cyan/40 bg-command-cyan/10 text-command-cyan" : "border-slate-700/60 bg-slate-950/55 text-slate-300"}`}
          onClick={() => setOnlyManual((current) => !current)}
          type="button"
        >
          {onlyManual ? "Showing manual only" : "Show manual only"}
        </button>
      }
    >
      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Total" value={summary.total} tone="cyan" />
        <TelemetryStat label="GO" value={summary.goCount} tone="green" />
        <TelemetryStat label="Manual Review" value={summary.manualCount} tone="amber" />
        <TelemetryStat label="Capacity Remaining" value={summary.operatorCapacityRemaining} tone={summary.operatorCapacityRemaining < 200 ? "amber" : "green"} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StateBadge state="ready" />
        <StateBadge state="stale" />
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Queue lag {summary.queueLagMinutes} minutes
        </div>
      </div>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "title", header: "RFQ", sortable: true, render: (row) => <div className="font-bold text-white">{row.title}</div>, sortValue: (row) => row.title, className: "min-w-[220px]" },
            { key: "province", header: "Province", sortable: true, render: (row) => row.province, sortValue: (row) => row.province },
            { key: "value", header: "Value", sortable: true, render: (row) => row.value, sortValue: (row) => Number(String(row.value).replace(/[^0-9.-]/g, "")) },
            { key: "profit", header: "Profit", sortable: true, render: (row) => row.profit, sortValue: (row) => Number(String(row.profit).replace(/[^0-9.-]/g, "")) },
            { key: "recommendation", header: "Recommendation", sortable: true, render: (row) => <StateBadge state={row.recommendation === "GO" ? "ready" : "stale"} />, sortValue: (row) => row.recommendation },
          ]}
          defaultSortKey="profit"
          description="Queued work remains operator-guided; no submission actions are exposed."
          emptyMessage="No review queue items available."
          loading={false}
          onRowClick={() => undefined}
          pageSize={6}
          rowKey={(row) => row.id}
          rows={filteredItems}
          searchAccessor={(row) => `${row.title} ${row.province} ${row.recommendation} ${row.id}`}
          searchPlaceholder="Search review queue"
          title="Queue Items"
        />
      </div>
    </SectionPanel>
  );
}
