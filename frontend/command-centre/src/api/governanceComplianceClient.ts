import { axiosAdapter } from "./axiosAdapter";
import { buildFallbackGovernanceSnapshot, safeArray, safeObject } from "./governanceHelpers";
import { buildFallbackGovernanceSnapshot as fallbackSnapshot } from "./governanceHelpers";

function normalizeComplianceReport(payload) {
  const source = safeObject(payload);
  const fallback = fallbackSnapshot();
  return {
    status: String(source.status || fallback.status || "runtime_fallback"),
    generatedAt: String(source.generated_at || source.generatedAt || fallback.generatedAt),
    dataSource: String(source.data_source || source.dataSource || fallback.dataSource || "runtime_fallback"),
    policies: safeObject(source.policies || fallback.policies),
    policyVersions: safeObject(source.policy_versions || source.policyVersions || fallback.policyVersions),
    complianceControls: safeObject(source.controls || source.complianceControls || fallback.complianceControls),
    accessReview: safeObject(source.access_review || source.accessReview || fallback.accessReview),
    attestations: safeObject(source.attestations || fallback.attestations),
    auditValidation: safeObject(source.audit_validation || source.auditValidation || fallback.auditValidation),
    auditMonitor: safeObject(source.audit_monitor || source.auditMonitor || fallback.auditMonitor),
    auditSnapshot: safeObject(source.audit_snapshot || source.auditSnapshot || fallback.auditSnapshot),
    retention: safeObject(source.retention || fallback.retention),
    legalHolds: safeObject(source.legal_holds || source.legalHolds || fallback.legalHolds),
    riskRegister: safeObject(source.risk_register || source.riskRegister || fallback.riskRegister),
    policyAcknowledgements: safeObject(source.policy_acknowledgements || source.policyAcknowledgements || fallback.policyAcknowledgements),
    regulatoryExport: safeObject(source.regulatory_export || source.regulatoryExport || fallback.regulatoryExport),
    complianceReport: safeObject(source.compliance_report || source.complianceReport || source),
  };
}

export async function fetchGovernanceComplianceSnapshot() {
  const remote = await axiosAdapter("/governance/compliance-report");
  if (remote) {
    return normalizeComplianceReport(remote);
  }
  return buildFallbackGovernanceSnapshot();
}

export async function fetchGovernancePolicies() {
  const remote = await axiosAdapter("/governance/policies");
  return remote || buildFallbackGovernanceSnapshot().policies;
}

export async function fetchComplianceControls() {
  const remote = await axiosAdapter("/governance/compliance-controls");
  return remote || buildFallbackGovernanceSnapshot().complianceControls;
}

