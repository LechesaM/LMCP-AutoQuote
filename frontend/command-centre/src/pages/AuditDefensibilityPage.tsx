import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import AuditIntegrityPanel from "../components/governance/AuditIntegrityPanel.tsx";
import EvidenceChainPanel from "../components/governance/EvidenceChainPanel.tsx";
import ComplianceExportPanel from "../components/governance/ComplianceExportPanel.tsx";
import { useAuditDefensibility } from "../hooks/useAuditDefensibility";
import { formatInteger } from "../utils/formatters";

export default function AuditDefensibilityPage() {
  const data = useAuditDefensibility();
  const auditIntegrity = data.auditIntegrity || {};

  return (
    <div className="space-y-6">
      <SectionPanel title="Audit Defensibility" description="Audit chain integrity, evidence continuity and export readiness." state={data.stale ? "stale" : data.refreshing ? "refreshing" : "ready"}>
        <div className="grid gap-3 md:grid-cols-3">
          <TelemetryStat label="Integrity Score" value={formatInteger(auditIntegrity.integrityScore || auditIntegrity.integrity_score || 0)} tone="green" />
          <TelemetryStat label="Missing Fields" value={formatInteger(auditIntegrity.missingRequiredFields || auditIntegrity.missing_required_fields || 0)} tone="amber" />
          <TelemetryStat label="Orphaned Actions" value={formatInteger((auditIntegrity.orphanedActions || auditIntegrity.orphaned_actions || []).length)} tone="red" />
        </div>
      </SectionPanel>
      <AuditIntegrityPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} onRetry={data.refresh} />
      <EvidenceChainPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
      <ComplianceExportPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
    </div>
  );
}
