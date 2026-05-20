import { axiosAdapter } from "./axiosAdapter";
import { buildFallbackGovernanceSnapshot, safeObject } from "./governanceHelpers";

function normalizeComplianceReporting(payload) {
  const source = safeObject(payload);
  const fallback = buildFallbackGovernanceSnapshot();
  return {
    status: String(source.status || fallback.status || "runtime_fallback"),
    generatedAt: String(source.generated_at || source.generatedAt || fallback.generatedAt),
    dataSource: String(source.data_source || source.dataSource || fallback.dataSource || "runtime_fallback"),
    complianceReport: safeObject(source.compliance_report || source.complianceReport || source),
    exportBundle: safeObject(source.regulatory_export || source.exportBundle || fallback.regulatoryExport),
    attestation: safeObject(source.attestations || source.attestation || fallback.attestations),
    policyAcknowledgements: safeObject(source.policy_acknowledgements || source.policyAcknowledgements || fallback.policyAcknowledgements),
    legalHolds: safeObject(source.legal_holds || source.legalHolds || fallback.legalHolds),
    accessReview: safeObject(source.access_review || source.accessReview || fallback.accessReview),
  };
}

export async function fetchComplianceReportingSnapshot() {
  const [complianceReport, regulatoryExport, attestation] = await Promise.all([
    axiosAdapter("/governance/compliance-report"),
    axiosAdapter("/governance/regulatory-export"),
    axiosAdapter("/governance/attestations"),
  ]);
  if (complianceReport || regulatoryExport || attestation) {
    return normalizeComplianceReporting({
      status: complianceReport?.status || regulatoryExport?.status || attestation?.status || "runtime_fallback",
      generated_at: complianceReport?.generated_at || regulatoryExport?.generated_at || attestation?.generated_at || new Date().toISOString(),
      data_source: complianceReport?.data_source || regulatoryExport?.data_source || attestation?.data_source || "runtime_fallback",
      compliance_report: complianceReport || {},
      regulatory_export: regulatoryExport || {},
      attestations: attestation || {},
      policy_acknowledgements: complianceReport?.policy_acknowledgements || {},
      legal_holds: complianceReport?.legal_holds || {},
      access_review: complianceReport?.access_review || {},
    });
  }
  return {
    ...buildFallbackGovernanceSnapshot(),
    complianceReport: buildFallbackGovernanceSnapshot(),
    exportBundle: {},
    attestation: {},
    policyAcknowledgements: {},
    legalHolds: {},
    accessReview: {},
  };
}

