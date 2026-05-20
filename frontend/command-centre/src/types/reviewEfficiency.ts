import type { ReviewQueueOptimizationItem } from "./reviewQueue";

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

