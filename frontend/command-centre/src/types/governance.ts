export type GovernancePolicy = {
  policyKey: string;
  title: string;
  category: string;
  description: string;
  version: string;
  status: string;
  effectiveAt: string;
  effectiveDate: string;
  supersededBy: string | null;
  manualEnforcementOnly: boolean;
  controls: string[];
  approvalMetadata: {
    approvedByRole: string;
    approvedBy: string;
    approvedAt: string;
  };
};

export type GovernanceComplianceReport = {
  status: string;
  generatedAt: string;
  dataSource: string;
  policies: { summary: { policyCount: number; categories: string[]; manualEnforcementOnly: boolean }; policies: GovernancePolicy[] };
  policyVersions: { policyVersions: Array<Record<string, unknown>>; supersededPolicies: unknown[] };
  complianceControls: Record<string, unknown>;
  accessReview: Record<string, unknown>;
  attestations: Record<string, unknown>;
  auditValidation: Record<string, unknown>;
  auditMonitor: Record<string, unknown>;
  auditSnapshot: Record<string, unknown>;
  retention: Record<string, unknown>;
  legalHolds: Record<string, unknown>;
  riskRegister: Record<string, unknown>;
  policyAcknowledgements: Record<string, unknown>;
  regulatoryExport: Record<string, unknown>;
};

export type GovernanceAuditDefensibility = {
  status: string;
  generatedAt: string;
  dataSource: string;
  auditIntegrity: Record<string, unknown>;
  accessReview: Record<string, unknown>;
  legalHolds: Record<string, unknown>;
  retention: Record<string, unknown>;
  regulatoryExport: Record<string, unknown>;
  evidenceChain: Record<string, unknown>;
};

export type GovernanceComplianceReporting = {
  status: string;
  generatedAt: string;
  dataSource: string;
  complianceReport: GovernanceComplianceReport;
  exportBundle: Record<string, unknown>;
  attestation: Record<string, unknown>;
  policyAcknowledgements: Record<string, unknown>;
  legalHolds: Record<string, unknown>;
  accessReview: Record<string, unknown>;
};

