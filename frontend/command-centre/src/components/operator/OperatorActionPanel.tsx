import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import RFQReviewActionBar from "./RFQReviewActionBar.tsx";

export default function OperatorActionPanel({ selectedRFQ, onAction, loading = false, disabled = false }) {
  const title = selectedRFQ?.title || selectedRFQ?.tenderId || "Selected RFQ";
  const recommendation = selectedRFQ?.recommendation || selectedRFQ?.qualificationState || "MANUAL_REVIEW";

  return (
    <SectionPanel title="Operator Actions" description="Controlled, confirmation-based operator operations." state={loading ? "loading" : "ready"}>
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Tender" value={selectedRFQ?.tenderId || "None"} tone="cyan" />
        <TelemetryStat label="Recommendation" value={recommendation} tone={recommendation === "GO" ? "green" : recommendation === "REJECT" ? "red" : "amber"} />
        <TelemetryStat label="Status" value={disabled ? "Disabled" : "Manual only"} tone="amber" />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="font-bold text-white">{title}</div>
        <div className="mt-2 text-slate-400">Actions require explicit operator intent and are appended to the audit timeline.</div>
      </div>
      <div className="mt-4">
        <RFQReviewActionBar rfq={selectedRFQ || {}} onAction={onAction} loading={loading} disabled={disabled} />
      </div>
    </SectionPanel>
  );
}
