import SectionPanel from "../ui/SectionPanel.tsx";

export default function OperatorEfficiencyPanel({ reviewEfficiency }) {
  return (
    <SectionPanel title="Review Efficiency" description="Throughput, evidence handling and queue aging." state={reviewEfficiency?.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="Reviewed / hr" value={Number(reviewEfficiency?.rfqsReviewedPerHour || 0).toFixed(1)} />
        <Metric label="Completion time" value={`${Number(reviewEfficiency?.reviewCompletionTimeMinutes || 0).toFixed(1)}m`} />
        <Metric label="Evidence time" value={`${Number(reviewEfficiency?.evidenceHandlingTimeMinutes || 0).toFixed(1)}m`} />
        <Metric label="Escalations" value={reviewEfficiency?.escalationFrequency || 0} />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
        <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Throughput Bottlenecks</div>
        <div className="mt-3 space-y-2">
          {(reviewEfficiency?.throughputBottlenecks || []).slice(0, 6).map((item) => (
            <div key={item.tenderId} className="rounded-2xl border border-slate-800/70 bg-slate-950/55 px-3 py-2 text-sm text-slate-300">
              {item.title}
            </div>
          ))}
        </div>
      </div>
    </SectionPanel>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
      <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-black text-white">{value}</div>
    </div>
  );
}

