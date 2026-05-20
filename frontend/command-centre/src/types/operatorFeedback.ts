import type { StabilizationOperatorFatigue, StabilizationRuntimeCleanup } from "./runtimeStability";

export type OperatorFeedbackSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  fatigue: StabilizationOperatorFatigue;
  feedback: {
    status: string;
    generatedAt: string;
    dataSource: string;
    painPoints: string[];
    trendSummary: Record<string, unknown>;
    feedbackItems: Array<{ label: string; value: string }>;
    operationalSignals: Record<string, unknown>;
  };
  cleanup: StabilizationRuntimeCleanup;
};
