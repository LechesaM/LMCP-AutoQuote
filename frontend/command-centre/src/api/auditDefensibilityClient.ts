import { axiosAdapter } from "./axiosAdapter";
import { buildFallbackGovernanceSnapshot, safeObject } from "./governanceHelpers";

function normalizeAuditDefensibility(payload) {
  const source = safeObject(payload);
  const fallback = buildFallbackGovernanceSnapshot();
  return {
    status: String(source.status || fallback.auditValidation.status || "runtime_fallback"),
    generatedAt: String(source.generated_at || source.generatedAt || fallback.generatedAt),
    dataSource: String(source.data_source || source.dataSource || fallback.dataSource || "runtime_fallback"),
    auditIntegrity: safeObject(source.audit_integrity || source.auditIntegrity || fallback.auditValidation),
    accessReview: safeObject(source.access_review || source.accessReview || fallback.accessReview),
    legalHolds: safeObject(source.legal_holds || source.legalHolds || fallback.legalHolds),
    retention: safeObject(source.retention || fallback.retention),
    regulatoryExport: safeObject(source.regulatory_export || source.regulatoryExport || fallback.regulatoryExport),
    evidenceChain: safeObject(source.evidence_chain || source.evidenceChain || fallback.auditSnapshot?.evidenceChain || {}),
  };
}

export async function fetchAuditDefensibilitySnapshot() {
  const [auditIntegrity, accessReview, retention, legalHolds, regulatoryExport] = await Promise.all([
    axiosAdapter("/governance/audit-integrity"),
    axiosAdapter("/governance/access-review"),
    axiosAdapter("/governance/retention-status"),
    axiosAdapter("/governance/legal-holds"),
    axiosAdapter("/governance/regulatory-export"),
  ]);
  if (auditIntegrity || accessReview || retention || legalHolds || regulatoryExport) {
    return normalizeAuditDefensibility({
      status: auditIntegrity?.status || accessReview?.status || retention?.status || legalHolds?.status || regulatoryExport?.status || "runtime_fallback",
      generated_at: auditIntegrity?.generated_at || accessReview?.generated_at || retention?.generated_at || legalHolds?.generated_at || regulatoryExport?.generated_at || new Date().toISOString(),
      data_source: auditIntegrity?.data_source || accessReview?.data_source || retention?.data_source || legalHolds?.data_source || regulatoryExport?.data_source || "runtime_fallback",
      audit_integrity: auditIntegrity || {},
      access_review: accessReview || {},
      retention: retention || {},
      legal_holds: legalHolds || {},
      regulatory_export: regulatoryExport || {},
      evidence_chain: regulatoryExport?.bundle?.audit_snapshot?.evidenceChain || {},
    });
  }
  return buildFallbackGovernanceSnapshot();
}

