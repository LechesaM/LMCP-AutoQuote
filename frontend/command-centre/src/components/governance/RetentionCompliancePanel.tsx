import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import { formatInteger } from "../../utils/formatters";

export default function RetentionCompliancePanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const retention = data?.retention || {};
  const holds = Array.isArray(data?.legalHolds?.holds) ? data.legalHolds.holds : [];
  const windows = retention?.retentionPolicy?.windows_days || retention?.retentionPolicy?.windowsDays || retention?.windowsDays || retention?.windows_days || {};

  return (
    <SectionPanel
      title="Retention Compliance"
      description="Retention windows, legal hold coverage and dry-run enforcement."
      state={state}
      actions={onRetry ? <button className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-xs font-black uppercase tracking-[.24em] text-command-cyan" onClick={onRetry} type="button">Refresh</button> : null}
    >
      {error ? <div className="mb-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Active Holds" value={formatInteger(data?.legalHolds?.activeCount || data?.legalHolds?.active_count || 0)} description="Protected records" tone="amber" />
        <TelemetryStat label="Dry-Run Only" value={String(Boolean(retention?.dryRunOnly ?? retention?.dry_run_only ?? true))} description="No destructive retention" tone="green" />
        <TelemetryStat label="Explicit Confirmation" value={String(Boolean(retention?.requiresExplicitConfirmation ?? retention?.requires_explicit_confirmation ?? true))} description="Manual retention actions only" tone="cyan" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Retention windows</div>
          <div className="mt-3 grid gap-2 text-sm text-slate-300">
            {Object.entries(windows || {}).length ? Object.entries(windows).map(([key, value]) => <div key={key} className="flex items-center justify-between"><span>{key}</span><span>{formatInteger(value)} days</span></div>) : <div className="text-slate-500">No retention windows found.</div>}
          </div>
        </div>
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Legal holds</div>
          <div className="mt-3 grid gap-2 text-sm text-slate-300">
            {holds.length ? holds.map((hold: any) => <div key={hold.hold_id || hold.holdId} className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-3 py-2"><div className="font-bold text-white">{hold.scope}</div><div className="text-xs text-slate-400">{hold.reason}</div></div>) : <EmptyTelemetryState title="No active legal holds" description="Retention is operating without protected hold scopes." />}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
