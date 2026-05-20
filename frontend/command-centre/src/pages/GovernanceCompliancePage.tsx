import { ShieldCheck, ClipboardList, AlertTriangle } from "lucide-react";
import SectionPanel from "../components/ui/SectionPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import PolicyRegistryPanel from "../components/governance/PolicyRegistryPanel.tsx";
import RetentionCompliancePanel from "../components/governance/RetentionCompliancePanel.tsx";
import GovernanceRiskPanel from "../components/governance/GovernanceRiskPanel.tsx";
import { useGovernanceCompliance } from "../hooks/useGovernanceCompliance";
import { formatInteger } from "../utils/formatters";

export default function GovernanceCompliancePage() {
  const data = useGovernanceCompliance();
  const controls = data.complianceControls || {};

  return (
    <div className="space-y-6">
      <SectionPanel title="Governance Compliance" description="Policy registry, retention enforcement and compliance controls." state={data.stale ? "stale" : data.refreshing ? "refreshing" : "ready"}>
        <div className="grid gap-3 md:grid-cols-3">
          <TelemetryStat label="Compliance Score" value={formatInteger(controls.complianceScore || controls.compliance_score || 0)} description="Advisory only" tone="green" />
          <TelemetryStat label="Warnings" value={formatInteger((controls.warnings || []).length)} description="Requires review" tone="amber" />
          <TelemetryStat label="Blockers" value={formatInteger((controls.blockers || []).length)} description="Must be resolved" tone="red" />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-400">
          <span className="flex items-center gap-2"><ShieldCheck size={16} className="text-command-green" /> Manual governance only</span>
          <span className="flex items-center gap-2"><ClipboardList size={16} className="text-command-cyan" /> Retention dry-run by default</span>
          <span className="flex items-center gap-2"><AlertTriangle size={16} className="text-command-amber" /> Audit defensibility monitored</span>
        </div>
      </SectionPanel>
      <PolicyRegistryPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} onRetry={data.refresh} />
      <RetentionCompliancePanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} onRetry={data.refresh} />
      <GovernanceRiskPanel data={data} loading={data.loading} refreshing={data.refreshing} stale={data.stale} error={data.error} />
    </div>
  );
}
