import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import { formatInteger } from "../../utils/formatters";

export default function AuditIntegrityPanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const auditIntegrity = data?.auditIntegrity || {};
  const evidenceChain = data?.evidenceChain || {};

  return (
    <SectionPanel
      title="Audit Integrity"
      description="Append-only audit chain validation and evidence continuity."
      state={state}
      actions={onRetry ? <button className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-xs font-black uppercase tracking-[.24em] text-command-cyan" onClick={onRetry} type="button">Refresh</button> : null}
    >
      {error ? <div className="mb-4 rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Integrity Score" value={formatInteger(auditIntegrity.integrityScore || auditIntegrity.integrity_score || 0)} description="Defensibility score" tone="green" />
        <TelemetryStat label="Missing Events" value={formatInteger(auditIntegrity.missingRequiredFields || auditIntegrity.missing_required_fields || 0)} description="Audit continuity gaps" tone="amber" />
        <TelemetryStat label="Evidence Chains" value={formatInteger(evidenceChain.evidenceEventCount || evidenceChain.evidence_event_count || 0)} description="Linked proof trail" tone="cyan" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center justify-between">
            <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Validation status</div>
            <StateBadge state={auditIntegrity.status || "ready"} />
          </div>
          <div className="mt-3 text-sm text-slate-300">Append-only: {String(Boolean(auditIntegrity.appendOnlyAssumed ?? auditIntegrity.append_only_assumed ?? true))}</div>
          <div className="mt-1 text-sm text-slate-300">Timestamps sorted: {String(Boolean(auditIntegrity.timestampsSorted ?? auditIntegrity.timestamps_sorted ?? true))}</div>
          <div className="mt-1 text-sm text-slate-300">Duplicate IDs: {String(Boolean(auditIntegrity.duplicateIds ?? auditIntegrity.duplicate_ids ?? false))}</div>
        </div>
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Warnings</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {Array.isArray(auditIntegrity.warnings) && auditIntegrity.warnings.length ? auditIntegrity.warnings.map((item: string, index: number) => <div key={`${item}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-3 py-2">{item}</div>) : <EmptyTelemetryState title="No integrity warnings" description="The audit chain is currently stable." />}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
