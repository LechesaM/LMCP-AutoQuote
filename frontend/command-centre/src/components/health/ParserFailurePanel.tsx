import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { useSourceHealth } from "../../hooks/useSourceHealth";

export default function ParserFailurePanel() {
  const { summary, rows, dataSource } = useSourceHealth();
  const failing = rows.filter((row) => Number(row.parserFailureRate || 0) > 0.1 || row.status !== "healthy");
  const parserFailureRate = rows.length
    ? rows.reduce((total, row) => total + Number(row.parserFailureRate || 0), 0) / rows.length
    : Number(summary.parserFailureRate || 0);

  return (
    <SectionPanel title="Parser Failure Trends" description="Observed parser failures and stale evidence sources." state={dataSource === "runtime" ? "ready" : "stale"}>
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Parser Failure Rate" value={parserFailureRate.toFixed(2)} tone="amber" />
        <TelemetryStat label="Failing Sources" value={failing.length} tone="red" />
        <TelemetryStat label="Healthy Sources" value={summary.healthySources} tone="green" />
      </div>

      <div className="mt-4 space-y-3">
        {failing.length ? (
          failing.slice(0, 5).map((source) => (
            <div key={source.sourceId} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-black text-white">{source.name}</div>
                  <div className="mt-1 text-xs text-slate-400">{source.sourceTier} · {source.parserType}</div>
                </div>
                <StateBadge state={source.status === "healthy" ? "ready" : "stale"} />
              </div>
              <div className="mt-3 text-sm text-slate-300">
                Failure rate {Number(source.parserFailureRate || 0).toFixed(2)} · Failures {source.failureCount} · Response {source.averageResponseTimeMs || 0}ms
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-400">No parser failure trends are currently visible.</div>
        )}
      </div>
    </SectionPanel>
  );
}
