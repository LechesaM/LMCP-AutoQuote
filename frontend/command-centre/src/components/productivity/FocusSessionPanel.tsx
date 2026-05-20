import SectionPanel from "../ui/SectionPanel.tsx";

export default function FocusSessionPanel({ sessions = [], summary = {} }) {
  return (
    <SectionPanel title="Focus Sessions" description="Focused work periods and interruption analysis." state={sessions.length ? "ready" : "empty"}>
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Sessions" value={summary.sessionCount || sessions.length || 0} />
        <Metric label="Throughput" value={summary.totalThroughput || 0} />
        <Metric label="Interruptions" value={summary.totalInterruptions || 0} />
      </div>
      <div className="mt-4 space-y-3">
        {sessions.slice(0, 6).map((session) => (
          <div key={session.operatorId + session.sessionStart} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-black text-white">{session.operatorId}</div>
              <div className="text-xs uppercase tracking-[.24em] text-slate-500">{session.focusedMinutes} min focused</div>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-4">
              <Metric label="Throughput" value={session.reviewThroughput} />
              <Metric label="Interruptions" value={session.interruptionCount} />
              <Metric label="Bursts" value={session.completionBursts} />
              <Metric label="Window" value={`${session.sessionStart || "n/a"} → ${session.sessionEnd || "n/a"}`} />
            </div>
          </div>
        ))}
      </div>
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

