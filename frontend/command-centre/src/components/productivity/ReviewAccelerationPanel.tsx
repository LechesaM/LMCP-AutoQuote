import SectionPanel from "../ui/SectionPanel.tsx";

export default function ReviewAccelerationPanel({ evidenceAcceleration }) {
  return (
    <SectionPanel title="Evidence Acceleration" description="Missing evidence, stale items and pricing mismatch summaries." state={evidenceAcceleration?.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Missing Evidence" value={evidenceAcceleration?.summary?.missingEvidence || evidenceAcceleration?.missingEvidence?.length || 0} />
        <Metric label="Stale Evidence" value={evidenceAcceleration?.summary?.staleEvidence || evidenceAcceleration?.staleEvidence?.length || 0} />
        <Metric label="Pricing Mismatches" value={evidenceAcceleration?.summary?.pricingMismatches || evidenceAcceleration?.pricingMismatchSummary?.length || 0} />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
        <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Grouped Warnings</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(evidenceAcceleration?.groupedWarnings || {}).map(([label, value]) => (
            <span key={label} className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
              {label}: {String(value)}
            </span>
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

