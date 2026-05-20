import SectionPanel from "../ui/SectionPanel.tsx";

export default function GovernanceTrendPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};

  return (
    <SectionPanel title="Governance Trends" description="Audit completeness, proof capture gaps and bypass observations." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Governance incidents: {summary.governanceIncidents || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Review bypass attempts: {summary.reviewBypassAttempts || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Proof capture gaps: {summary.proofCaptureGaps || 0}</div>
      </div>
      <div className="mt-4 text-sm text-slate-300">
        Manual approval, review_ready, proof capture and final submission remain human-governed.
      </div>
    </SectionPanel>
  );
}

