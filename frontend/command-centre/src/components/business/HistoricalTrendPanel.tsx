import SectionPanel from "../ui/SectionPanel.tsx";

export default function HistoricalTrendPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const weekly = Array.isArray(data?.trendWindows?.week) ? data.trendWindows.week : Array.isArray(data?.weeklyTrend) ? data.weeklyTrend : [];
  const monthly = Array.isArray(data?.trendWindows?.month) ? data.trendWindows.month : Array.isArray(data?.monthlyTrend) ? data.monthlyTrend : [];
  return (
    <SectionPanel title="Historical Trends" description="Rolling windows and seasonal patterns." state={state}>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Weekly</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {weekly.slice(0, 4).map((row: any) => (
              <div key={row.label} className="flex items-center justify-between">
                <span>{row.label}</span>
                <span className="font-black">{Number(row.count || 0)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Monthly</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {monthly.slice(0, 4).map((row: any) => (
              <div key={row.label} className="flex items-center justify-between">
                <span>{row.label}</span>
                <span className="font-black">{Number(row.count || 0)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}

