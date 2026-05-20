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

