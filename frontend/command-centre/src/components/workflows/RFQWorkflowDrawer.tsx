import Drawer from "../ui/Drawer.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import RFQQualificationPanel from "./RFQQualificationPanel.tsx";
import RFQPricingEvidencePanel from "./RFQPricingEvidencePanel.tsx";
import RFQGovernancePanel from "./RFQGovernancePanel.tsx";

function renderList(values, emptyLabel) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  if (!items.length) {
    return <div className="text-sm text-slate-400">{emptyLabel}</div>;
  }
  return (
    <div className="space-y-2">
      {items.map((value, index) => (
        <div key={`${String(value)}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
          {typeof value === "string" ? value : JSON.stringify(value)}
        </div>
      ))}
    </div>
  );
}

export default function RFQWorkflowDrawer({ open, detail, loading = false, error = "", onClose }) {
  const summary = detail?.summary || {};
  const qualification = detail?.qualificationSummary || {};
  const riskSummary = detail?.riskSummary || {};
  const pricingEvidence = detail?.pricingEvidence || {};
  const pricingValidation = detail?.pricingValidation || {};
  const pricingTraceability = detail?.pricingTraceability || {};
  const governanceSummary = detail?.governanceSummary || {};

  return (
    <Drawer
      open={open}
      onClose={onClose}
      subtitle={detail?.dataSourceLabel ? `Data source: ${detail.dataSourceLabel}` : "Read-only RFQ detail"}
      title={summary.title || detail?.tenderId || "RFQ Detail"}
    >
      {loading ? <div className="glass-card rounded-3xl p-5 text-sm text-slate-400">Loading RFQ detail…</div> : null}
      {error ? <div className="glass-card rounded-3xl border border-command-red/30 bg-command-red/10 p-5 text-sm text-slate-200">{error}</div> : null}

      {!loading && !error && detail ? (
        <div className="space-y-4">
          <SectionPanel title="RFQ Summary" description="Operationally visible summary only." state="ready">
            <div className="grid gap-3 md:grid-cols-4">
              <TelemetryStat label="Buyer" value={summary.buyer || "Unknown"} tone="cyan" />
              <TelemetryStat label="Province" value={summary.province || "Unknown"} tone="green" />
              <TelemetryStat label="Workflow Stage" value={summary.workflowStage || "unknown"} tone="amber" />
              <TelemetryStat label="Review Status" value={summary.reviewStatus || "manual_review_required"} tone="slate" />
            </div>
          </SectionPanel>

          <RFQQualificationPanel qualification={qualification} row={detail?.summary || {}} />

          <SectionPanel title="Risk Summary" description="Qualification risk and operational blockers." state="ready">
            <div className="grid gap-3 md:grid-cols-3">
              <TelemetryStat label="Risk Level" value={String(riskSummary.risk_level || riskSummary.riskLevel || detail?.qualificationSummary?.risk_level || "medium")} tone="amber" />
              <TelemetryStat label="Overall Risk" value={String(riskSummary.overall_risk || riskSummary.overallRisk || 0)} tone="amber" />
              <TelemetryStat label="Manual Review Triggers" value={Array.isArray(detail?.manualReviewTriggers) ? detail.manualReviewTriggers.length : 0} tone="cyan" />
            </div>
          </SectionPanel>

          <RFQPricingEvidencePanel pricingEvidence={pricingEvidence} pricingValidation={pricingValidation} pricingTraceability={pricingTraceability} row={detail?.summary || {}} />

          <RFQGovernancePanel governanceSummary={governanceSummary} />

          <SectionPanel title="Workflow History" description="Read-only history of workflow stages." state="ready">
            {renderList(detail.workflowHistory, "No workflow history captured.")}
          </SectionPanel>

          <div className="grid gap-4 lg:grid-cols-2">
            <SectionPanel title="Recommendation Reasons" description="Why this RFQ received its recommendation." state="ready">
              {renderList(detail.recommendationReasons, "No recommendation reasons captured.")}
            </SectionPanel>
            <SectionPanel title="Operational Warnings" description="Non-blocking observations from live telemetry." state="ready">
              {renderList(detail.operationalWarnings, "No operational warnings captured.")}
            </SectionPanel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <SectionPanel title="Manual Review Triggers" description="Operator attention required." state="ready">
              {renderList(detail.manualReviewTriggers, "No manual review triggers captured.")}
            </SectionPanel>
            <SectionPanel title="Disqualification Triggers" description="Reasons this RFQ may be rejected or held." state="ready">
              {renderList(detail.disqualificationTriggers, "No disqualification triggers captured.")}
            </SectionPanel>
          </div>

          <SectionPanel title="Source Health" description="Source-specific operating state for this RFQ." state="ready">
            {renderList(Object.entries(detail.sourceHealth || {}).map(([key, value]) => `${key}: ${String(value)}`), "No source health details captured.")}
          </SectionPanel>
        </div>
      ) : null}
    </Drawer>
  );
}
