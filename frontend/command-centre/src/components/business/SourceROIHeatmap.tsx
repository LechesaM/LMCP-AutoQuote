import SectionPanel from "../ui/SectionPanel.tsx";

function rowClass(score: number) {
  if (score >= 70) return "border-command-green/30 bg-command-green/10";
  if (score <= 30) return "border-command-red/30 bg-command-red/10";
  return "border-command-amber/30 bg-command-amber/10";
}

export default function SourceROIHeatmap({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const rows = [...(data?.topValueSources || []), ...(data?.lowValueSources || []), ...(data?.noisySources || [])].slice(0, 12);

  return (
    <SectionPanel title="Source ROI Heatmap" description="Top value, low value and noisy procurement sources." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row: any) => (
          <div key={`${row.sourceId || row.name}`} className={`rounded-2xl border p-4 ${rowClass(Number(row.roiScore || 0))}`}>
            <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">{row.tier || "Source"}</div>
            <div className="mt-2 text-sm font-black text-white">{row.name}</div>
            <div className="mt-2 text-xs text-slate-300">ROI score {Number(row.roiScore || 0).toFixed(1)}</div>
          </div>
        ))}
      </div>
    </SectionPanel>
  );
}

