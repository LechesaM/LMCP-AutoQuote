import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import StateBadge from "../ui/StateBadge.tsx";

export default function PolicyRegistryPanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const policies = Array.isArray(data?.policies?.policies) ? data.policies.policies : [];

  return (
    <SectionPanel
      title="Policy Registry"
      description="Governance policy catalog and versioning."
      state={state}
      actions={onRetry ? <button className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-xs font-black uppercase tracking-[.24em] text-command-cyan" onClick={onRetry} type="button">Refresh</button> : null}
    >
      {error ? <div className="mb-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      {policies.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {policies.map((policy: any) => (
            <div key={policy.policyKey || policy.policy_key} className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-black text-white">{policy.title}</div>
                  <div className="mt-1 text-xs uppercase tracking-[.22em] text-slate-500">{policy.category}</div>
                </div>
                <StateBadge state={policy.status || "ready"} />
              </div>
              <div className="mt-3 text-sm text-slate-300">{policy.description}</div>
              <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-black uppercase tracking-[.2em] text-slate-400">
                <span>v{policy.version}</span>
                <span>{Boolean(policy.manualEnforcementOnly ?? policy.manual_enforcement_only) ? "manual only" : "automated"}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyTelemetryState title="No policies loaded" description="The governance registry is using a safe fallback snapshot." />
      )}
    </SectionPanel>
  );
}
