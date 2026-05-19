import { useMemo } from "react";
import { useSourceHealth } from "../../hooks/useSourceHealth";
import DataTable from "../ui/DataTable.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";

export default function SourceHealthTable() {
  const { rows, summary, tierBreakdown, loading, refreshing, error, dataSource, generatedAt, refresh } = useSourceHealth();

  const sortedRows = useMemo(() => [...rows].sort((left, right) => (right.failureCount || 0) - (left.failureCount || 0)), [rows]);

  return (
    <SectionPanel
      title="Source Health"
      description="Harvest source counts, parser states and recent failures."
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
      <div className="grid gap-3 md:grid-cols-5">
        <TelemetryStat label="Total Sources" value={summary.totalSources} tone="cyan" />
        <TelemetryStat label="Healthy" value={summary.healthySources} tone="green" />
        <TelemetryStat label="Degraded" value={summary.degradedSources} tone="amber" />
        <TelemetryStat label="Failing" value={summary.failingSources} tone="red" />
        <TelemetryStat label="Disabled" value={summary.disabledSources} tone="slate" />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {Object.entries(tierBreakdown || {}).map(([tier, count]) => (
          <div key={tier} className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300">
            {tier}: {String(count)}
          </div>
        ))}
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300">
          Last updated {generatedAt || "unknown"}
        </div>
      </div>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "name", header: "Source", sortable: true, render: (row) => <div className="font-bold text-white">{row.name}</div>, sortValue: (row) => row.name, className: "min-w-[180px]" },
            { key: "sourceTier", header: "Tier", sortable: true, render: (row) => row.sourceTier, sortValue: (row) => row.sourceTier },
            { key: "parserType", header: "Parser", sortable: true, render: (row) => row.parserType, sortValue: (row) => row.parserType },
            { key: "status", header: "Status", sortable: true, render: (row) => row.status, sortValue: (row) => row.status },
            { key: "lastSuccess", header: "Last Success", sortable: true, render: (row) => row.lastSuccess || "—", sortValue: (row) => row.lastSuccess || "" },
            { key: "lastFailure", header: "Last Failure", sortable: true, render: (row) => row.lastFailure || "—", sortValue: (row) => row.lastFailure || "" },
            { key: "failureCount", header: "Failures", sortable: true, render: (row) => row.failureCount, sortValue: (row) => row.failureCount },
            { key: "averageResponseTimeMs", header: "Latency", sortable: true, render: (row) => `${row.averageResponseTimeMs || 0} ms`, sortValue: (row) => row.averageResponseTimeMs || 0 },
            { key: "parserFailureRate", header: "Parser Failure Rate", sortable: true, render: (row) => `${Number(row.parserFailureRate || 0).toFixed(2)}`, sortValue: (row) => row.parserFailureRate || 0 },
            { key: "healthState", header: "Health", sortable: true, render: (row) => row.healthState, sortValue: (row) => row.healthState },
          ]}
          defaultSortKey="failureCount"
          description="Source health is read-only and derived from runtime telemetry."
          emptyMessage="No source health records available."
          loading={loading}
          onRetry={refresh}
          pageSize={8}
          rowKey={(row) => row.sourceId}
          rows={sortedRows}
          searchAccessor={(row) => `${row.name} ${row.sourceTier} ${row.parserType} ${row.status} ${row.healthState}`}
          searchPlaceholder="Search source health"
          stale={dataSource !== "runtime"}
          title="Source Health Records"
        />
      </div>
    </SectionPanel>
  );
}
