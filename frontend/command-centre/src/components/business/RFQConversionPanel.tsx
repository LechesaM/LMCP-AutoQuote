import SectionPanel from "../ui/SectionPanel.tsx";

export default function RFQConversionPanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};
  return (
    <SectionPanel title="RFQ Conversion" description="Harvested → qualified → reviewed → submission-ready conversion." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["Harvested", summary.harvested],
          ["Qualified", summary.qualified],
          ["Reviewed", summary.reviewed],
          ["Submission-ready", summary.submission_ready],
        ].map(([label, value]) => (
          <div key={label as string} className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-500">{label}</div>
            <div className="mt-2 text-2xl font-black text-white">{String(value ?? 0)}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Harvested → qualified: {Number(data?.conversionRates?.harvested_to_qualified || 0).toFixed(2)}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Qualified → reviewed: {Number(data?.conversionRates?.qualified_to_reviewed || 0).toFixed(2)}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Reviewed → ready: {Number(data?.conversionRates?.reviewed_to_submission_ready || 0).toFixed(2)}</div>
      </div>
    </SectionPanel>
  );
}

