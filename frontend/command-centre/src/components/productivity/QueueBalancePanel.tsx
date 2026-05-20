import SectionPanel from "../ui/SectionPanel.tsx";

export default function QueueBalancePanel({ queueOptimization, workload }) {
  return (
    <SectionPanel title="Queue Balance" description="Optimized ordering and operating pressure." state={queueOptimization?.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Urgent" value={queueOptimization?.summary?.urgent || 0} />
        <Metric label="High" value={queueOptimization?.summary?.high || 0} />
        <Metric label="Average Age" value={`${Number(queueOptimization?.summary?.averageQueueAgeMinutes || 0).toFixed(1)}m`} />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        {workload?.remainingCapacity <= 200
          ? "Operator capacity is tight. Prioritize urgent work and keep bulk actions confirmed and minimal."
          : "Capacity is available. Maintain manual review cadence and keep the queue balanced."}
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

