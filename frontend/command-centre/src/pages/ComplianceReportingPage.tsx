import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import AttestationPanel from "../components/governance/AttestationPanel.tsx";
import ComplianceExportPanel from "../components/governance/ComplianceExportPanel.tsx";
import AccessReviewPanel from "../components/governance/AccessReviewPanel.tsx";
import LegalHoldPanel from "../components/governance/LegalHoldPanel.tsx";
import PolicyAcknowledgementPanel from "../components/governance/PolicyAcknowledgementPanel.tsx";
import { useComplianceReporting } from "../hooks/useComplianceReporting";
import { formatInteger } from "../utils/formatters";

export default function ComplianceReportingPage() {
  const data = useComplianceReporting();
  const report = data.complianceReport || {};

  return (
    <div className="space-y-6">
      <SectionPanel title="Compliance Reporting" description="Attestations, legal holds, access review and export readiness." state={data.stale ? "stale" : data.refreshing ? "refreshing" : "ready"}>
        <div className="grid gap-3 md:grid-cols-3">
          <TelemetryStat label="Policies" value={formatInteger((report.policies?.policies || []).length || 0)} tone="cyan" />
          <TelemetryStat label="Acknowledgements" value={formatInteger((data.policyAcknowledgements?.acknowledgements || data.policyAcknowledgements?.acknowledgements || []).length || 0)} tone="amber" />
          <TelemetryStat label="Legal Holds" value={formatInteger((data.legalHolds?.holds || []).length || 0)} tone="green" />
        </div>
      </SectionPanel>
      <AttestationPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
      <ComplianceExportPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
      <AccessReviewPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
      <LegalHoldPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
      <PolicyAcknowledgementPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
    </div>
  );
}
