export type StabilizationTrend = {
  label: string;
  value: number;
  healthy: number;
  degraded: number;
  failing: number;
};

export type StabilizationCheck = {
  label: string;
  status: string;
  passed: boolean;
  detail: string;
  severity: string;
};

export type StabilizationOperatorRow = {
  operatorId: string;
  workloadScore: number;
  fatigueScore: number;
  warning: string;
  recommendation: string;
  overdueReviews: number;
  repeatedEscalations: number;
  prolongedQueueExposure: number;
  focusSessionExhaustion: number;
};

export type StabilizationRuntime = {
  status: string;
  generatedAt: string;
  dataSource: string;
  stabilityScore: number;
  degradationTrends: StabilizationTrend[];
  operationalWarnings: string[];
  snapshotHealth: Record<string, unknown>;
  queueLagMinutes: number;
  telemetryFreshnessMinutes: number;
  workerStaleCount: number;
  sourceFailureCount: number;
  alertCount: number;
  anomalyCount: number;
  windowSize: number;
  signals: Record<string, unknown>;
};

export type StabilizationFallbackHealth = {
  status: string;
  generatedAt: string;
  dataSource: string;
  fallbackHealthSummary: Record<string, unknown>;
  fallbackActivations: number;
  staleFallbacks: number;
  runtimeRecoverySuccess: boolean;
  recoverySuccessRate: number;
  warnings: string[];
  blockers: string[];
  advisoryOnly: boolean;
};

export type StabilizationTelemetryNoise = {
  status: string;
  generatedAt: string;
  dataSource: string;
  alerts: Array<Record<string, unknown>>;
  alertGroups: Array<{ label: string; count: number; severity: string }>;
  severityCounts: Record<string, unknown>;
  suppressedCount: number;
  retainedCount: number;
  criticalCount: number;
  noiseScore: number;
  advisoryOnly: boolean;
};

export type StabilizationGovernanceConsistency = {
  status: string;
  generatedAt: string;
  dataSource: string;
  consistencyScore: number;
  checks: StabilizationCheck[];
  inconsistencies: string[];
  warnings: string[];
  blockers: string[];
  auditAttributionMissing: boolean;
  roleDistribution: Record<string, unknown>;
  permissions: string[];
};

export type StabilizationOperatorFatigue = {
  status: string;
  generatedAt: string;
  dataSource: string;
  fatigueScore: number;
  warnings: string[];
  fatigueRows: StabilizationOperatorRow[];
  workloadRebalanceRecommendations: string[];
  signals: Record<string, unknown>;
};

export type StabilizationOperatorFeedback = {
  status: string;
  generatedAt: string;
  dataSource: string;
  painPoints: string[];
  trendSummary: Record<string, unknown>;
  feedbackItems: Array<{ label: string; value: string }>;
  operationalSignals: Record<string, unknown>;
};

export type StabilizationRuntimeCleanup = {
  status: string;
  generatedAt: string;
  dataSource: string;
  dryRunOnly: boolean;
  confirmed: boolean;
  cleanupSummary: Record<string, unknown>;
  wouldCleanup: Array<{ label: string; count: number }>;
  warnings: string[];
  blockers: string[];
};

export type StabilizationDeployment = {
  status: string;
  generatedAt: string;
  dataSource: string;
  deploymentStabilityScore: number;
  startupReadiness: Record<string, unknown>;
  runtimeIntegrity: Record<string, unknown>;
  environmentSummary: Record<string, unknown>;
  persistenceHealth: Record<string, unknown>;
  queueSummary: Record<string, unknown>;
  routeAvailability: Record<string, unknown>;
  routeNames: string[];
  warnings: string[];
  startupBlockers: string[];
  blockers: string[];
  authAvailable: boolean;
  persistenceAvailable: boolean;
  queueAvailable: boolean;
  observabilityAvailable: boolean;
};

export type RuntimeStabilizationSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  runtimeStability: StabilizationRuntime;
  fallbackHealth: StabilizationFallbackHealth;
  telemetryNoise: StabilizationTelemetryNoise;
  governanceConsistency: StabilizationGovernanceConsistency;
  deploymentStability: StabilizationDeployment;
};

export type RuntimeReliabilitySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  runtimeStability: StabilizationRuntime;
  fallbackHealth: StabilizationFallbackHealth;
  telemetryNoise: StabilizationTelemetryNoise;
  deploymentStability: StabilizationDeployment;
  summary: {
    stabilityScore: number;
    fallbackActivations: number;
    noiseScore: number;
    deploymentScore: number;
  };
};
