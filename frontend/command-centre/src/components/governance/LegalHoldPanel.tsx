import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import { formatInteger } from "../../utils/formatters";

export default function LegalHoldPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const holds = Array.isArray(data?.legalHolds?.holds) ? data.legalHolds.holds : [];
  return (
    <SectionPanel title="Legal Holds" description="Protected retention scopes and release trail." state={state}>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Active Holds</div>
          <div className="mt-2 text-3xl font-black text-white">{formatInteger(data?.legalHolds?.activeCount || 0)}</div>
        </div>
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Total Holds</div>
          <div className="mt-2 text-3xl font-black text-white">{formatInteger(holds.length)}</div>
        </div>
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Release Trail</div>
          <div className="mt-2 text-3xl font-black text-white">{formatInteger(holds.filter((hold: any) => !hold.active).length)}</div>
        </div>
      </div>
      <div className="mt-4">
        {holds.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {holds.map((hold: any) => (
              <div key={hold.hold_id || hold.holdId} className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
                <div className="font-black text-white">{hold.scope}</div>
                <div className="mt-1 text-slate-400">{hold.reason}</div>
                <div className="mt-2 text-xs uppercase tracking-[.22em] text-slate-500">{hold.active ? "active" : "released"}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyTelemetryState title="No legal holds" description="There are no active protected retention objects." />
        )}
      </div>
    </SectionPanel>
  );
}

