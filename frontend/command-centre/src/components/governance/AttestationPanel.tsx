import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import ActionBadge from "../ui/ActionBadge.tsx";

export default function AttestationPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const attestationResponse = data?.attestation || data?.attestations || {};
  const attestation = attestationResponse.attestation || attestationResponse;
  const attestationText = data?.attestationText || attestationResponse.attestationText || attestationResponse.attestation_text || "";
  return (
    <SectionPanel title="Governance Attestation" description="Signed-style statement of manual-only governance." state={state}>
      <div className="flex flex-wrap items-center gap-3">
        <StateBadge state={state} />
        <ActionBadge action={Boolean(attestation.noAutonomousSubmission ?? attestation.no_autonomous_submission) ? "manual only" : "review"} tone={Boolean(attestation.noAutonomousSubmission ?? attestation.no_autonomous_submission) ? "green" : "amber"} />
        <ActionBadge action={Boolean(attestation.proofCaptureEnforced ?? attestation.proof_capture_enforced) ? "proof capture" : "missing evidence"} tone={Boolean(attestation.proofCaptureEnforced ?? attestation.proof_capture_enforced) ? "cyan" : "red"} />
      </div>
      <div className="mt-4 rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        {attestationText || "Governance attestation is available when the compliance API is connected."}
      </div>
      <div className="mt-3 text-xs uppercase tracking-[.24em] text-slate-500">Signature: {attestation.signature || "runtime-fallback"}</div>
    </SectionPanel>
  );
}
