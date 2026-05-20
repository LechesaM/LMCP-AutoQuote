import { Users2, AlertTriangle } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";

export default function OperatorWorkloadPanel({ workload }) {
  const operators = workload?.operators || [];
  return (
    <SectionPanel title="Operator Workload" description="Balanced assignments, overdue reviews and utilization." state={workload?.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Capacity</div>
          <div className="mt-2 text-3xl font-black text-white">{workload?.remainingCapacity ?? 0} left</div>
          <div className="mt-1 text-sm text-slate-400">{workload?.assignedToday ?? 0}/{workload?.totalDailyCapacity ?? 1000} used</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Average Utilization</div>
          <div className="mt-2 text-3xl font-black text-white">{Number(workload?.averageUtilization || 0).toFixed(1)}%</div>
          <div className="mt-1 text-sm text-slate-400">Across {workload?.teamSize ?? 10} operators</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Average Score</div>
          <div className="mt-2 text-3xl font-black text-white">{Number(workload?.averageWorkloadScore || 0).toFixed(1)}</div>
          <div className="mt-1 text-sm text-slate-400">Higher indicates heavier queue pressure</div>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {operators.slice(0, 8).map((row) => (
          <div key={row.operatorId} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-command-cyan/10 text-command-cyan">
                  <Users2 size={17} />
                </div>
                <div>
                  <div className="font-black text-white">{row.operatorId}</div>
                  <div className="text-xs uppercase tracking-[.2em] text-slate-500">{row.specialization}</div>
                </div>
              </div>
              {row.overdue > 0 ? (
                <div className="flex items-center gap-2 rounded-full border border-command-amber/40 bg-command-amber/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-command-amber">
                  <AlertTriangle size={12} />
                  Overdue {row.overdue}
                </div>
              ) : null}
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-4">
              <Metric label="Assigned" value={row.assigned} />
              <Metric label="Utilization" value={`${Number(row.utilization || 0).toFixed(1)}%`} />
              <Metric label="Timeline" value={row.timelineEvents} />
              <Metric label="Workload" value={Number(row.workloadScore || 0).toFixed(1)} />
            </div>
          </div>
        ))}
      </div>
      {workload?.overloadWarnings?.length ? <div className="mt-4 rounded-2xl border border-command-red/30 bg-command-red/10 p-3 text-sm text-slate-200">{workload.overloadWarnings.join(" · ")}</div> : null}
      {workload?.underutilizationWarnings?.length ? <div className="mt-3 rounded-2xl border border-command-cyan/30 bg-command-cyan/10 p-3 text-sm text-slate-200">{workload.underutilizationWarnings.join(" · ")}</div> : null}
    </SectionPanel>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-800/70 bg-slate-950/55 p-3">
      <div className="text-[10px] font-black uppercase tracking-[.22em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-black text-white">{value}</div>
    </div>
  );
}

