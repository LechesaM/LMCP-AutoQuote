import ReviewAccelerationPanel from "../components/productivity/ReviewAccelerationPanel.tsx";
import OperatorEfficiencyPanel from "../components/productivity/OperatorEfficiencyPanel.tsx";
import FocusSessionPanel from "../components/productivity/FocusSessionPanel.tsx";
import useReviewEfficiency from "../hooks/useReviewEfficiency";

export default function ReviewEfficiencyPage() {
  const efficiency = useReviewEfficiency();
  return (
    <div className="space-y-6">
      <header className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Review Efficiency</div>
            <h1 className="mt-2 text-3xl font-black text-white">Throughput, evidence handling and review aging</h1>
            <p className="mt-2 text-sm text-slate-400">Operational analytics for productivity without any change to workflow governance.</p>
          </div>
          <Badge label={efficiency.dataSource} />
        </div>
      </header>

      <OperatorEfficiencyPanel reviewEfficiency={efficiency.reviewEfficiency} />
      <FocusSessionPanel sessions={efficiency.focusSessions.sessions} summary={efficiency.focusSessions.summary} />
      <ReviewAccelerationPanel evidenceAcceleration={efficiency.evidenceAcceleration} />
    </div>
  );
}

function Badge({ label }) {
  return <span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{label}</span>;
}

