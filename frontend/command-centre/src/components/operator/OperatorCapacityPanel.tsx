import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { useOperatorCapacity } from "../../hooks/useOperatorCapacity";

export default function OperatorCapacityPanel({ snapshot = null }) {
  const live = useOperatorCapacity();
  const capacity = snapshot || live;
  const state = capacity.loading ? "loading" : capacity.error ? "error" : capacity.refreshing ? "refreshing" : capacity.stale ? "stale" : "ready";

  return (
    <SectionPanel
      title="Operator Capacity"
      description="10 operators, 100 RFQs/day each, 1,000/day total. Recommendations only."
      state={state}
      actions={<StateBadge state={capacity.dataSource === "runtime" ? "ready" : "stale"} />}
    >
      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Team Size" value={capacity.teamSize} tone="cyan" />
        <TelemetryStat label="Per Operator" value={capacity.perOperatorDailyCapacity} tone="green" />
        <TelemetryStat label="Total Capacity" value={capacity.totalDailyCapacity} tone="amber" />
        <TelemetryStat label="Remaining" value={capacity.remaining} tone={capacity.remaining < 200 ? "red" : "green"} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Assigned today: <span className="font-bold text-white">{capacity.assignedToday}</span>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Utilization: <span className="font-bold text-white">{capacity.totalDailyCapacity ? capacity.utilization.toFixed(1) : "0.0"}%</span>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Recommended load: <span className="font-bold text-white">{capacity.recommendedLoad}</span>
        </div>
      </div>
      <div className="mt-4 rounded-2xl border border-command-green/30 bg-command-green/10 px-4 py-3 text-sm text-slate-200">
        Capacity is advisory. The system does not promote work beyond capacity limits.
      </div>
    </SectionPanel>
  );
}
