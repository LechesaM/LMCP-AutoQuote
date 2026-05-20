import useAuthStore from "../auth/authStore";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

export const nowIso = () => new Date().toISOString();

export const safeArray = (value) => (Array.isArray(value) ? value : []);

export const safeObject = (value) => (value && typeof value === "object" && !Array.isArray(value) ? value : {});

export function buildFallbackGovernanceSnapshot() {
  const telemetry = useTelemetryStore.getState();
  const queue = useQueueStore.getState();
  const sourceHealth = useSourceHealthStore.getState();
  const user = useAuthStore.getState().user;
  return {
    status: "runtime_fallback",
    generatedAt: nowIso(),
    dataSource: "runtime_fallback",
    policies: {
      summary: {
        policyCount: 6,
        categories: ["workflow", "records", "access", "audit"],
        manualEnforcementOnly: true,
      },
      policies: [],
    },
    policyVersions: { policyVersions: [], supersededPolicies: [] },
    complianceControls: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      complianceScore: 100,
      warnings: ["Runtime fallback governance snapshot."],
      blockers: [],
      controls: {
        review_ready_enforced: true,
        proof_capture_enforced: true,
        operator_attribution_required: true,
        audit_completeness: true,
        retention_compliance: true,
        rbac_integrity: true,
        manual_submission_only: true,
      },
      manualGovernanceOnly: true,
    },
    accessReview: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      activeUsers: user ? [user] : [],
      roleDistribution: user ? { [String(user.role || "unknown")]: 1 } : {},
      privilegedAccess: [],
      staleSessions: [],
      warnings: [],
    },
    attestations: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      attestation: {
        manualOnlyGovernance: true,
        noAutonomousSubmission: true,
        proofCaptureEnforced: true,
        auditCompleteness: true,
        retentionCompliance: true,
        rbacEnforcement: true,
        signature: "",
      },
      attestationText: "Fallback governance attestation.",
      signedStyle: false,
      exportSafe: true,
    },
    auditValidation: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      totalEvents: 0,
      missingRequiredFields: 0,
      timestampsSorted: true,
      duplicateIds: false,
      orphanedActions: [],
      warnings: [],
      blockers: [],
      integrityScore: 100,
      appendOnlyAssumed: true,
    },
    auditMonitor: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      integrityScore: 100,
      warnings: [],
      blockers: [],
    },
    auditSnapshot: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      auditEvents: { status: "ok", items: [], total: 0 },
      auditSummary: { status: "ok", summary: { totalEvents: 0 } },
      auditIntegrity: { status: "ok", integrityScore: 100 },
      evidenceChain: { evidenceEventCount: 0, evidenceChainComplete: true },
      exportReady: true,
    },
    retention: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      dryRunOnly: true,
      requiresExplicitConfirmation: true,
      retentionPolicy: {},
    },
    legalHolds: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      holds: [],
      activeCount: 0,
    },
    riskRegister: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      risks: [],
      summary: { low: 0, medium: 0, high: 0, critical: 0 },
      warnings: [],
      blockers: [],
    },
    policyAcknowledgements: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      acknowledgements: [],
      acknowledgementCount: 0,
    },
    regulatoryExport: {
      status: "runtime_fallback",
      generatedAt: nowIso(),
      dataSource: "runtime_fallback",
      bundle: {},
      manifest: {},
      exportSafe: true,
      noSecrets: true,
      manualGovernanceOnly: true,
    },
    reviewSummary: queue.summary || {},
    sourceSummary: sourceHealth.summary || {},
    telemetrySummary: telemetry.commandMetrics || {},
  };
}

