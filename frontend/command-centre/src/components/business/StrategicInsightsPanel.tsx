import SectionPanel from "../ui/SectionPanel.tsx";

export default function StrategicInsightsPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const insights = Array.isArray(data?.strategicHighlights) ? data.strategicHighlights : [];
  return (
    <SectionPanel title="Strategic Insights" description="Advisory-only executive takeaways." state={state}>
      <div className="grid gap-2">
        {insights.length ? (
          insights.map((insight: string, index: number) => (
            <div key={`${insight}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
              {insight}
            </div>
          ))
        ) : (
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-sm text-slate-400">
            No strategic insights available.
          </div>
        )}
      </div>
    </SectionPanel>
  );
}

