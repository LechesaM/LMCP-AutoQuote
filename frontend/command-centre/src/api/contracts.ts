import type { DashboardTelemetry } from "../types/telemetry";

export type ApiEnvelope<T> = {
  data: T;
  meta?: Record<string, unknown>;
};

export type ReviewQueueResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  items: ReviewQueueEntry[];
  summary?: ReviewQueueSummary;
};

export type ReviewQueueEntry = {
  id: string;
  title: string;
  province: string;
  value: string;
  profit: string;
  recommendation: string;
};

export type ReviewQueueSummary = {
  total: number;
  goCount: number;
  manualCount: number;
  alerts: string[];
  pendingReviews?: number;
  approvedToday?: number;
  manualReviewRequired?: number;
  blockedReviews?: number;
  overdueReviews?: number;
  operatorCapacity?: number;
  operatorCapacityUsed?: number;
  operatorCapacityRemaining?: number;
  queueLagMinutes?: number;
};

export type HarvestHealthResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  sources: SourceHealthEntry[];
  totalSources: number;
  activeSources: number;
  healthySources: number;
  degradedSources: number;
  failingSources: number;
  disabledSources: number;
  parserFailureRate: number;
  averageResponseTimeMs: number;
  recentSourceFailures: SourceFailureEntry[];
};

export type SourceHealthEntry = {
  id: string;
  name: string;
  tier: string;
  active: boolean;
  eligible: number;
  total: number;
  status?: string;
  failureCount?: number;
  parserFailureRate?: number;
  evidenceStale?: boolean;
  lastUpdatedAt?: string;
};

export type SourceFailureEntry = {
  sourceId: string;
  name: string;
  status: string;
  failureCount: number;
  consecutiveFailures: number;
  parserFailureRate?: number;
};

export type QualificationSummaryResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  goCount: number;
  manualReviewCount: number;
  rejectCount: number;
  lowConfidenceCount: number;
  topRejectionReasons: string[];
  topManualReviewTriggers: string[];
  avgQualificationScore: number;
  avgRiskScore: number;
  manualGovernanceOnly: boolean;
  reviewReadyRequired: boolean;
  proofCaptureRequired: boolean;
};

export type ReviewQueueTelemetryResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  pendingReviews: number;
  approvedToday: number;
  manualReviewRequired: number;
  blockedReviews: number;
  overdueReviews: number;
  operatorCapacity: number;
  operatorCapacityUsed: number;
  operatorCapacityRemaining: number;
  queueLagMinutes: number;
};

export type OperationalHealthTelemetryResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  sourceFailures: number;
  parserFailures: number;
  queueLag: number;
  operatorCapacity: number;
  rfqAging: number;
  staleEvidence: number;
  workflowFailures: number;
  persistenceFailures: number;
  auditFailures: number;
  governanceComplianceScore: number;
  manualGovernanceIntegrityScore: number;
};

export type { DashboardTelemetry };
