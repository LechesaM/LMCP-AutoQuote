import OperatorEfficiencyPanel from "../components/productivity/OperatorEfficiencyPanel.tsx";
import OperatorShortcutPanel from "../components/productivity/OperatorShortcutPanel.tsx";
import OperatorWorkloadPanel from "../components/productivity/OperatorWorkloadPanel.tsx";
import FocusSessionPanel from "../components/productivity/FocusSessionPanel.tsx";
import useOperatorProductivity from "../hooks/useOperatorProductivity";

export default function OperatorProductivityPage() {
  const productivity = useOperatorProductivity();
  return (
    <div className="space-y-6">
      <header className="glass-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.26em] text-command-cyan">Operator Productivity</div>
            <h1 className="mt-2 text-3xl font-black text-white">Review throughput and operator ergonomics</h1>
            <p className="mt-2 text-sm text-slate-400">Balanced workload, focus sessions and governed shortcuts for supervised-live review work.</p>
          </div>
          <Badge label={productivity.dataSource} />
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          <Badge label={productivity.loading ? "Loading" : productivity.refreshing ? "Refreshing" : productivity.stale ? "Stale" : "Current"} />
          <Badge label={`Updated ${productivity.lastUpdated || "unknown"}`} />
          {productivity.error ? <Badge label="Refresh error" tone="amber" /> : null}
        </div>
      </header>

      <OperatorWorkloadPanel workload={productivity.workload} />
      <FocusSessionPanel sessions={productivity.focusSessions.sessions} summary={productivity.focusSessions.summary} />
      <OperatorEfficiencyPanel reviewEfficiency={productivity.reviewEfficiency} />
      <OperatorShortcutPanel shortcuts={productivity.shortcuts} />
    </div>
  );
}

function Badge({ label, tone = "slate" }) {
  const palette = tone === "amber" ? "border-command-amber/40 bg-command-amber/10 text-command-amber" : "border-slate-700/60 bg-slate-950/55 text-slate-300";
  return <span className={`rounded-full border px-3 py-1 ${palette}`}>{label}</span>;
}

