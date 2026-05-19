export type RFQWorkflowRow = {
  tenderId: string;
  title: string;
  buyer: string;
  province: string;
  qualificationState: string;
  estimatedProfit: number;
  estimatedMargin: number;
  riskLevel: string;
  workflowStage: string;
  reviewStatus: string;
  pricingConfidence: number;
  sourceTier: string;
  submissionMethod: string;
  dataSource: string;
  lastUpdated: string;
  qualification?: Record<string, unknown>;
  pricingEvidence?: Record<string, unknown>;
  pricingTraceability?: Record<string, unknown>;
};

export type RFQWorkflowHistoryEntry = {
  tenderId: string;
  stage: string;
  updatedAt: string;
  details?: Record<string, unknown>;
};

export type RFQWorkflowDetail = {
  status: string;
  generatedAt: string;
  dataSource: string;
  tenderId: string;
  summary: {
    title: string;
    buyer: string;
    province: string;
    workflowStage: string;
    reviewStatus: string;
  };
  qualificationSummary: Record<string, unknown>;
  riskSummary: Record<string, unknown>;
  pricingEvidence: Record<string, unknown>;
  pricingValidation: Record<string, unknown>;
  pricingTraceability: Record<string, unknown>;
  governanceSummary: Record<string, unknown>;
  workflowHistory: RFQWorkflowHistoryEntry[];
  operationalWarnings: string[];
  recommendationReasons: string[];
  manualReviewTriggers: string[];
  disqualificationTriggers: string[];
  sourceHealth: Record<string, unknown>;
  dataSourceLabel: string;
};

export type RFQWorkflowResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  summary: {
    total: number;
    go: number;
    manualReview: number;
    reject: number;
    dataSource: string;
  };
  rows: RFQWorkflowRow[];
};
