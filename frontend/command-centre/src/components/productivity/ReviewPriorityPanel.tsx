import SectionPanel from "../ui/SectionPanel.tsx";

export default function ReviewPriorityPanel({ priorities = {} }) {
  const groups = priorities.priorityGroups || {};
  return (
    <SectionPanel title="Review Priorities" description="Urgent work, escalation recommendations and queue pressure." state={priorities.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Urgent" value={groups.urgent?.length || 0} />
        <Metric label="High" value={groups.high?.length || 0} />
        <Metric label="Medium" value={groups.medium?.length || 0} />
        <Metric label="Low" value={groups.low?.length || 0} />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
        <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Escalation Recommendations</div>
        <div className="mt-3 space-y-2">
          {(priorities.escalationRecommendations || []).slice(0, 6).map((item, index) => (
            <div key={`${item.tenderId || index}`} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-800/70 bg-slate-950/55 px-3 py-2">
              <div>
                <div className="text-sm font-black text-white">{item.title || item.tenderId || "Unknown RFQ"}</div>
                <div className="text-xs text-slate-500">{item.reason || "Queue pressure"}</div>
              </div>
              <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">{item.recommendation || "monitor"}</div>
            </div>
          ))}
        </div>
      </div>
    </SectionPanel>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-center">
      <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-black text-white">{value}</div>
    </div>
  );
}

