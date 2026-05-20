import { AlertTriangle, Server, ShieldCheck } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function DeploymentStabilityPanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Deployment Stability" description="Environment, startup and route validation">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Deployment Stability"
      description="Validates deployment consistency, required env vars, route availability and backend startup readiness."
      state={snapshot?.status === "healthy" ? "ready" : snapshot?.blockers?.length ? "error" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Stability Score" value={formatNumber(snapshot?.deploymentStabilityScore)} description="Deployment hardening signal" tone={snapshot?.deploymentStabilityScore >= 80 ? "green" : "amber"} />
        <TelemetryStat label="Auth Available" value={snapshot?.authAvailable ? "Yes" : "No"} description="Auth middleware reachable" tone={snapshot?.authAvailable ? "green" : "red"} />
        <TelemetryStat label="Persistence Available" value={snapshot?.persistenceAvailable ? "Yes" : "No"} description="Persistence layer reachable" tone={snapshot?.persistenceAvailable ? "green" : "red"} />
        <TelemetryStat label="Queue Available" value={snapshot?.queueAvailable ? "Yes" : "No"} description="Queue backend reachable" tone={snapshot?.queueAvailable ? "green" : "red"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Server size={14} className="text-command-cyan" /> Startup Readiness
          </div>
          <pre className="mt-3 overflow-x-auto rounded-2xl border border-slate-800/70 bg-slate-950/50 p-3 text-[11px] leading-5 text-slate-300">
            {JSON.stringify(snapshot?.startupReadiness || {}, null, 2)}
          </pre>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <ShieldCheck size={14} className="text-command-green" /> Route & Environment Checks
          </div>
          <div className="mt-3 space-y-2">
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">Routes: {(snapshot?.routeNames || []).join(", ") || "none"}</div>
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">Observability available: {String(snapshot?.observabilityAvailable)}</div>
            {(snapshot?.warnings || []).map((warning) => (
              <div key={warning} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                {warning}
              </div>
            ))}
            {(snapshot?.blockers || []).map((blocker) => (
              <div key={blocker} className="rounded-2xl border border-command-red/20 bg-command-red/10 px-3 py-2 text-command-red">
                <span className="mr-2 inline-flex items-center gap-2">
                  <AlertTriangle size={13} /> Blocker
                </span>
                {blocker}
              </div>
            ))}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
