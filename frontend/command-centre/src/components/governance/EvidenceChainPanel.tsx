import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import { formatInteger } from "../../utils/formatters";

export default function EvidenceChainPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const evidence = data?.auditSnapshot?.evidenceChain || data?.evidenceChain || {};
  const events = Array.isArray(evidence.evidenceEvents) ? evidence.evidenceEvents : [];

  return (
    <SectionPanel title="Evidence Chain" description="Audit-linked evidence continuity and missing reference detection." state={state}>
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Evidence Events" value={formatInteger(evidence.evidenceEventCount || events.length || 0)} tone="cyan" />
        <TelemetryStat label="Missing References" value={formatInteger(Array.isArray(evidence.missingReferences) ? evidence.missingReferences.length : 0)} tone="amber" />
        <TelemetryStat label="Chain Complete" value={String(Boolean(evidence.evidenceChainComplete ?? true))} tone={evidence.evidenceChainComplete ? "green" : "red"} />
      </div>
      <div className="mt-4">
        {events.length ? (
          <div className="grid gap-2">
            {events.slice(0, 8).map((event: any, index: number) => (
              <div key={`${event.event_type || event.eventType || index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-3 py-2 text-sm text-slate-300">
                <div className="font-bold text-white">{event.event_type || event.eventType || "evidence event"}</div>
                <div className="text-xs text-slate-400">{event.created_at || event.createdAt || ""}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyTelemetryState title="No evidence chain entries" description="Audit-linked evidence will appear here when runtime records exist." />
        )}
      </div>
    </SectionPanel>
  );
}

