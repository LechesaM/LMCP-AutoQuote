import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";

export default function PolicyAcknowledgementPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const acknowledgements = Array.isArray(data?.policyAcknowledgements?.acknowledgements) ? data.policyAcknowledgements.acknowledgements : [];
  return (
    <SectionPanel title="Policy Acknowledgements" description="Operator acknowledgements and policy review trail." state={state}>
      {acknowledgements.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {acknowledgements.map((item: any) => (
            <div key={item.ack_id || item.ackId} className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
              <div className="font-black text-white">{item.policy_key}</div>
              <div className="mt-1 text-slate-400">{item.note}</div>
              <div className="mt-2 text-xs uppercase tracking-[.2em] text-slate-500">{item.acknowledged ? "acknowledged" : "pending"}</div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyTelemetryState title="No acknowledgements recorded" description="Policy acknowledgements will appear when operators review governance statements." />
      )}
    </SectionPanel>
  );
}

