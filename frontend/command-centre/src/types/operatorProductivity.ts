export type OperatorWorkloadItem = {
  operatorId: string;
  assigned: number;
  overdue: number;
  utilization: number;
  timelineEvents: number;
  specialization: string;
  workloadScore: number;
  averageDueAgeHours: number;
  priorityAverage: number;
};

export type OperatorWorkloadSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  teamSize: number;
  totalDailyCapacity: number;
  assignedToday: number;
  remainingCapacity: number;
  averageUtilization: number;
  averageWorkloadScore: number;
  overloadWarnings: string[];
  underutilizationWarnings: string[];
  operators: OperatorWorkloadItem[];
};

export type FocusSession = {
  operatorId: string;
  focusedMinutes: number;
  reviewThroughput: number;
  interruptionCount: number;
  completionBursts: number;
  sessionStart: string;
  sessionEnd: string;
};

export type ReviewQueueOptimizationItem = {
  tenderId: string;
  title: string;
  buyer: string;
  province: string;
  closingDate: string;
  workflowStage: string;
  reviewStatus: string;
  pricingConfidence: number;
  queueAgeMinutes: number;
  priorityScore: number;
  priorityGroup: string;
  priorityReason: string;
  riskLevel: string;
  staleEvidence: boolean;
  reviewReadiness: string;
  governanceBlocked: boolean;
  submissionMethod: string;
  sourceTier: string;
  dataSource: string;
};

export type ReviewQueueOptimizationSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  optimizedQueue: ReviewQueueOptimizationItem[];
  priorityGroups: Record<string, ReviewQueueOptimizationItem[]>;
  overdueReviews: ReviewQueueOptimizationItem[];
  staleRfqs: ReviewQueueOptimizationItem[];
  overloadedQueue: boolean;
  summary: {
    total: number;
    urgent: number;
    high: number;
    medium: number;
    low: number;
    averagePriorityScore: number;
    averageQueueAgeMinutes: number;
  };
};

export type ReviewEfficiencySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  rfqsReviewedPerHour: number;
  reviewCompletionTimeMinutes: number;
  evidenceHandlingTimeMinutes: number;
  escalationFrequency: number;
  reassignmentFrequency: number;
  queueAgingTrends: Record<string, unknown>;
  operatorThroughputTrends: Record<string, unknown>;
  timelineGapMinutes: number;
  throughputBottlenecks: ReviewQueueOptimizationItem[];
  advisoryOnly: boolean;
};

export type QueueHeatmapEntry = {
  axis: string;
  label: string;
  value: number;
};

export type QueueHeatmapSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  heatmap: QueueHeatmapEntry[];
  operatorDistribution: Record<string, number>;
  sourceDistribution: Record<string, number>;
  escalationDensity: Record<string, number>;
  provinceDensity: Record<string, number>;
};

export type ReviewPrioritySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  priorityScore: number;
  priorityGroups: Record<string, ReviewQueueOptimizationItem[]>;
  escalationRecommendations: Array<{ tenderId?: string; title?: string; recommendation?: string; reason?: string }>;
  reviewUrgency: string;
  overloadedQueue: boolean;
};

export type EvidenceAccelerationSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  missingEvidence: ReviewQueueOptimizationItem[];
  staleEvidence: ReviewQueueOptimizationItem[];
  supplierQuoteCompleteness: Array<{ tenderId?: string; title?: string; pricingConfidence?: number; queueAgeMinutes?: number }>;
  pricingMismatchSummary: ReviewQueueOptimizationItem[];
  groupedWarnings: Record<string, number>;
  summary: Record<string, unknown>;
};

export type ProductivitySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  workload: OperatorWorkloadSnapshot;
  queueOptimization: ReviewQueueOptimizationSnapshot;
  reviewEfficiency: ReviewEfficiencySnapshot;
  focusSessions: { status: string; generatedAt: string; dataSource: string; sessions: FocusSession[]; summary: Record<string, unknown>; advisoryOnly: boolean };
  queueHeatmap: QueueHeatmapSnapshot;
  reviewPriorities: ReviewPrioritySnapshot;
  evidenceAcceleration: EvidenceAccelerationSnapshot;
  shortcuts: { status: string; generatedAt: string; dataSource: string; shortcuts: Array<{ label: string; key: string; action: string }>; quickActions: string[]; filterPresets: string[]; advisoryOnly: boolean };
};

