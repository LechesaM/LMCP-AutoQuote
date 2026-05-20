import { ShieldAlert } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function SentryIncidentPanel({ sentry = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  if (loading) {
    return (
      <SectionPanel title="Sentry Status" description="Optional runtime exception capture." state="loading">
        <SkeletonCard lines={3} />
      </SectionPanel>
    );
  }
  const config = sentry.sentry || {};
  return (
    <SectionPanel
      title="Sentry Status"
      description="Optional exception capture with request ID correlation."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {sentry.dataSource || "fallback"}
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Enabled" value={String(Boolean(config.enabled))} description="Sentry capture status" tone={config.enabled ? "green" : "amber"} />
        <TelemetryStat label="DSN Configured" value={String(Boolean(config.dsnConfigured))} description="Secret-free configuration check" tone={config.dsnConfigured ? "green" : "amber"} />
        <TelemetryStat label="Environment" value={config.environment || "n/a"} description="Deployment environment tag" tone="cyan" />
        <TelemetryStat label="Sample Rate" value={`${Number(config.sampleRate || 0).toFixed(2)}`} description="Safe sample rate" tone="slate" />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <ShieldAlert size={14} className="text-command-amber" /> Operational Note
        </div>
        <div className="mt-2 text-slate-400">
          {config.enabled ? "Runtime exceptions can be correlated to request IDs." : "Sentry is disabled until LMCP_SENTRY_DSN and LMCP_ENABLE_SENTRY are configured."}
        </div>
      </div>
      {error ? <div className="mt-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
