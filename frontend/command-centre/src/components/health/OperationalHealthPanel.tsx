import { Activity, AlertTriangle, Clock3, DatabaseZap, Filter, GaugeCircle, RefreshCcw, ShieldAlert } from "lucide-react";
import StateCard from "../ui/StateCard.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";
import { useOperationalHealth } from "../../hooks/useOperationalHealth";

function StatTile({ label, value, tone = "slate", description = "" }) {
  const palette =
    tone === "green"
      ? "border-command-green/30 bg-command-green/10 text-command-green"
      : tone === "cyan"
        ? "border-command-cyan/30 bg-command-cyan/10 text-command-cyan"
        : tone === "amber"
          ? "border-command-amber/30 bg-command-amber/10 text-command-amber"
          : tone === "red"
            ? "border-command-red/30 bg-command-red/10 text-command-red"
            : "border-slate-700/60 bg-slate-950/45 text-slate-300";

  return (
    <div className={`rounded-2xl border p-4 ${palette}`}>
      <div className="text-[10px] font-black uppercase tracking-[.24em] opacity-85">{label}</div>
      <div className="mt-2 text-3xl font-black text-white">{value}</div>
      {description ? <div className="mt-1 text-xs text-slate-400">{description}</div> : null}
    </div>
  );
}

export default function OperationalHealthPanel({ state }) {
  const health = useOperationalHealth();
  const panelState = state || (health.loading ? "loading" : health.error && !health.dataSource ? "error" : health.stale ? "stale" : health.state);

  if (panelState === "loading") {
    return (
      <div className="glass-card rounded-3xl p-5">
        <SkeletonCard lines={6} />
      </div>
    );
  }

  if (panelState === "error") {
    return (
      <StateCard title="Operational Health" state="error" description="Operational telemetry could not be loaded.">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-command-red/15 text-command-red">
            <AlertTriangle size={18} />
          </div>
          <div className="text-sm text-slate-300">
            The panel failed to render, but command centre workflows remain available.
          </div>
        </div>
      </StateCard>
    );
  }

  return (
    <StateCard
      title="Operational Health"
      state={panelState}
      description="Source failures, parser failures, queue lag, operator capacity, RFQ aging, stale evidence and system failures."
      onRetry={health.refresh}
    >
      <div className="mb-4 flex flex-wrap gap-3">
        <StateBadge state={panelState} />
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {health.dataSource || "runtime_fallback"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {health.loading ? "Loading" : health.refreshing ? "Refreshing" : "Ready"}
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Last updated {health.lastUpdated || health.telemetryUpdatedAt || "unknown"}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <StatTile
          label="Source Failures"
          value={health.sourceFailures}
          tone={health.sourceFailures > 0 ? "red" : "green"}
          description="Non-healthy harvesting sources"
        />
        <StatTile
          label="Parser Failures"
          value={health.parserFailures}
          tone={health.parserFailures > 0 ? "amber" : "green"}
          description="Sources with elevated parser failure rate"
        />
        <StatTile
          label="Queue Lag"
          value={health.queueLag}
          tone={health.queueLag > 0 ? "amber" : "green"}
          description={health.queueLagLabel}
        />
        <StatTile
          label="Operator Capacity"
          value={`${health.operatorCapacity.remaining} left`}
          tone={health.operatorCapacity.remaining < 200 ? "amber" : "cyan"}
          description={`${health.operatorCapacity.used}/${health.operatorCapacity.total} used · ${health.operatorCapacity.utilization}% util`}
        />
        <StatTile
          label="RFQ Aging"
          value={health.rfqAging}
          tone={health.rfqAging > 40 ? "red" : health.rfqAging > 20 ? "amber" : "green"}
          description="Harvester backlog signal"
        />
        <StatTile
          label="Stale Evidence"
          value={health.staleEvidence}
          tone={health.staleEvidence > 0 ? "amber" : "green"}
          description="Evidence and alert staleness signals"
        />
        <StatTile
          label="Workflow Failures"
          value={health.workflowFailures || 0}
          tone={health.workflowFailures > 0 ? "red" : "green"}
          description="Workflow monitor failures"
        />
        <StatTile
          label="Persistence Failures"
          value={health.persistenceFailures || 0}
          tone={health.persistenceFailures > 0 ? "red" : "green"}
          description="Persistence health warnings"
        />
        <StatTile
          label="Audit Failures"
          value={health.auditFailures || 0}
          tone={health.auditFailures > 0 ? "red" : "green"}
          description="Audit trail and event delivery"
        />
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Activity size={14} className="text-command-green" />
            Telemetry
          </div>
          <div className="mt-2 text-sm text-slate-300">Last refresh: {health.telemetryUpdatedAt || "unknown"}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Clock3 size={14} className="text-command-cyan" />
            Queue
          </div>
          <div className="mt-2 text-sm text-slate-300">Last refresh: {health.queueUpdatedAt || "unknown"}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <DatabaseZap size={14} className="text-command-amber" />
            Sources
          </div>
          <div className="mt-2 text-sm text-slate-300">Last refresh: {health.sourceHealthUpdatedAt || "unknown"}</div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          <Filter className="mr-1 inline-block" size={12} />
          Governed telemetry only
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          <ShieldAlert className="mr-1 inline-block" size={12} />
          No submission bypass
        </div>
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          <RefreshCcw className="mr-1 inline-block" size={12} />
          Polling-ready
        </div>
      </div>
    </StateCard>
  );
}
