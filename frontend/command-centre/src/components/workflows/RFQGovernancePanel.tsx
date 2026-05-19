import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";

export default function RFQGovernancePanel({ governanceSummary = {} }) {
  const manualApproval = Boolean(governanceSummary.manual_approval_status ?? governanceSummary.manualApprovalStatus);
  const reviewReady = Boolean(governanceSummary.review_ready_status ?? governanceSummary.reviewReadyStatus);
  const proofCapture = Boolean(governanceSummary.proof_capture_status ?? governanceSummary.proofCaptureStatus);
  const supervisedLive = Boolean(governanceSummary.supervised_live_governance ?? governanceSummary.supervisedLiveGovernance ?? true);
  const manualSubmissionConfirmed = Boolean(governanceSummary.manual_submission_confirmed ?? governanceSummary.manualSubmissionConfirmed);
  const complianceScore = Number(governanceSummary.governance_compliance_score ?? governanceSummary.governanceComplianceScore ?? 0);
  const warnings = Array.isArray(governanceSummary.warnings) ? governanceSummary.warnings : governanceSummary.governanceWarnings || [];

  return (
    <SectionPanel title="Governance Summary" description="Manual approval, review_ready and proof capture remain governed by operators." state={manualApproval && reviewReady ? "ready" : "stale"}>
      <div className="rounded-2xl border border-command-green/30 bg-command-green/10 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StateBadge state={manualApproval && reviewReady ? "ready" : "stale"} />
          <div className="rounded-full border border-command-green/30 bg-command-green/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-command-green">
            Final submission remains manual-only
          </div>
        </div>
        <div className="mt-3 text-sm text-slate-200">
          The command centre preserves manual approval, review_ready confirmation and proof capture. No autonomous submission path is exposed here.
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Governance Score" value={complianceScore.toFixed(1)} tone="green" />
        <TelemetryStat label="Review Ready" value={reviewReady ? "Yes" : "No"} tone={reviewReady ? "green" : "amber"} />
        <TelemetryStat label="Proof Capture" value={proofCapture ? "Yes" : "No"} tone={proofCapture ? "green" : "amber"} />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Governance Flags</div>
          <div className="mt-3 space-y-2">
            <div>Manual approval: <span className="font-bold text-white">{manualApproval ? "confirmed" : "pending"}</span></div>
            <div>Review ready: <span className="font-bold text-white">{reviewReady ? "confirmed" : "pending"}</span></div>
            <div>Proof capture: <span className="font-bold text-white">{proofCapture ? "confirmed" : "pending"}</span></div>
            <div>Supervised-live governance: <span className="font-bold text-white">{supervisedLive ? "enabled" : "disabled"}</span></div>
            <div>Manual submission confirmed: <span className="font-bold text-white">{manualSubmissionConfirmed ? "yes" : "no"}</span></div>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Governance Warnings</div>
          <div className="mt-3 space-y-2">
            {warnings.length ? warnings.map((warning, index) => <div key={`${warning}-${index}`}>• {String(warning)}</div>) : <div>No governance warnings captured.</div>}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
