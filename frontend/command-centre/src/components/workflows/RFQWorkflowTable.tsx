import { useMemo, useState } from "react";
import { useRFQOperations } from "../../hooks/useRFQOperations";
import { formatCurrency, formatPercent } from "../../utils/formatters";
import DataTable from "../ui/DataTable.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";

const qualificationStates = ["ALL", "GO", "MANUAL_REVIEW", "REJECT"];

export default function RFQWorkflowTable({ onSelectRFQ, selectedTenderId = "" }) {
  const { rows, loading, refreshing, error, dataSource, generatedAt, refresh } = useRFQOperations();
  const [stateFilter, setStateFilter] = useState("ALL");

  const filteredRows = useMemo(() => {
    if (stateFilter === "ALL") {
      return rows;
    }
    return rows.filter((row) => String(row.qualificationState || "").toUpperCase() === stateFilter);
  }, [rows, stateFilter]);

  const summary = useMemo(
    () => ({
      total: rows.length,
      go: rows.filter((row) => row.qualificationState === "GO").length,
      manual: rows.filter((row) => row.qualificationState === "MANUAL_REVIEW").length,
      reject: rows.filter((row) => row.qualificationState === "REJECT").length,
    }),
    [rows],
  );

  return (
    <SectionPanel
      title="RFQ Workflow"
      description="Sortable, filterable and read-only RFQ operating view."
      state={loading ? "loading" : error ? "error" : refreshing ? "refreshing" : "ready"}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge state={dataSource === "runtime" ? "ready" : "stale"} />
          <button
            className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300"
            onClick={refresh}
            type="button"
          >
            Refresh
          </button>
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-500">Total</div>
          <div className="mt-2 text-3xl font-black text-white">{summary.total}</div>
        </div>
        <div className="rounded-2xl border border-command-green/30 bg-command-green/10 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-green">GO</div>
          <div className="mt-2 text-3xl font-black text-white">{summary.go}</div>
        </div>
        <div className="rounded-2xl border border-command-cyan/30 bg-command-cyan/10 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Manual Review</div>
          <div className="mt-2 text-3xl font-black text-white">{summary.manual}</div>
        </div>
        <div className="rounded-2xl border border-command-amber/30 bg-command-amber/10 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-amber">Reject</div>
          <div className="mt-2 text-3xl font-black text-white">{summary.reject}</div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {qualificationStates.map((state) => (
          <button
            key={state}
            className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] ${stateFilter === state ? "border-command-cyan/40 bg-command-cyan/10 text-command-cyan" : "border-slate-700/60 bg-slate-950/55 text-slate-300"}`}
            onClick={() => setStateFilter(state)}
            type="button"
          >
            {state}
          </button>
        ))}
      </div>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "tenderId", header: "RFQ ID", sortable: true, render: (row) => <div className="font-bold text-white">{row.tenderId}</div>, sortValue: (row) => row.tenderId, className: "min-w-[120px]" },
            { key: "title", header: "Title", sortable: true, render: (row) => row.title, sortValue: (row) => row.title, className: "min-w-[220px]" },
            { key: "buyer", header: "Buyer", sortable: true, render: (row) => row.buyer, sortValue: (row) => row.buyer },
            { key: "province", header: "Province", sortable: true, render: (row) => row.province, sortValue: (row) => row.province },
            { key: "qualificationState", header: "Qualification", sortable: true, render: (row) => <StateBadge state={row.qualificationState === "GO" ? "ready" : row.qualificationState === "REJECT" ? "error" : "stale"} />, sortValue: (row) => row.qualificationState },
            { key: "estimatedProfit", header: "Estimated Profit", sortable: true, render: (row) => formatCurrency(row.estimatedProfit), sortValue: (row) => row.estimatedProfit },
            { key: "estimatedMargin", header: "Margin", sortable: true, render: (row) => formatPercent(row.estimatedMargin), sortValue: (row) => row.estimatedMargin },
            { key: "riskLevel", header: "Risk", sortable: true, render: (row) => row.riskLevel, sortValue: (row) => row.riskLevel },
            { key: "workflowStage", header: "Stage", sortable: true, render: (row) => row.workflowStage, sortValue: (row) => row.workflowStage },
            { key: "reviewStatus", header: "Review", sortable: true, render: (row) => row.reviewStatus, sortValue: (row) => row.reviewStatus },
            { key: "pricingConfidence", header: "Pricing Confidence", sortable: true, render: (row) => `${Number(row.pricingConfidence || 0).toFixed(1)}%`, sortValue: (row) => row.pricingConfidence },
            { key: "sourceTier", header: "Source Tier", sortable: true, render: (row) => row.sourceTier, sortValue: (row) => row.sourceTier },
            { key: "submissionMethod", header: "Submission", sortable: true, render: (row) => row.submissionMethod, sortValue: (row) => row.submissionMethod },
            { key: "dataSource", header: "Data Source", sortable: true, render: (row) => row.dataSource, sortValue: (row) => row.dataSource },
            { key: "lastUpdated", header: "Last Updated", sortable: true, render: (row) => row.lastUpdated, sortValue: (row) => row.lastUpdated },
          ]}
          defaultSortKey="estimatedProfit"
          description={`Updated ${generatedAt || "unknown"} · ${dataSource || "runtime_fallback"}`}
          emptyMessage="No RFQ workflow rows available."
          loading={loading}
          onRowClick={(row) => onSelectRFQ?.(row.tenderId)}
          onRetry={refresh}
          pageSize={8}
          rowKey={(row) => row.tenderId}
          rows={filteredRows}
          searchAccessor={(row) => `${row.tenderId} ${row.title} ${row.buyer} ${row.province} ${row.workflowStage} ${row.reviewStatus} ${row.sourceTier} ${row.submissionMethod}`}
          searchPlaceholder="Search RFQ workflow"
          stale={dataSource !== "runtime"}
          title="Workflow Items"
        />
      </div>
    </SectionPanel>
  );
}
