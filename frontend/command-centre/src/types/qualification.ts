export type QualificationInsightsResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  summary: {
    recommendation_counts?: Record<string, number>;
    risk_breakdown?: Record<string, number>;
    average_automation_suitability_score?: number;
    blockers?: string[];
    manual_review_trigger_counts?: Record<string, number>;
  };
  provinceHeat: Record<string, Record<string, number>>;
  lowConfidenceRfqs: Array<Record<string, unknown>>;
  riskDistribution: Record<string, number>;
  qualificationScoreAverage: number;
  riskScoreAverage: number;
  topRejectionReasons: string[];
  topManualReviewTriggers: string[];
  goCount: number;
  manualReviewCount: number;
  rejectCount: number;
};
