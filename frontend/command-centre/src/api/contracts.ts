import type { DashboardTelemetry } from "../types/telemetry";

export type ApiEnvelope<T> = {
  data: T;
  meta?: Record<string, unknown>;
};

export type ReviewQueueResponse = {
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
};

export type HarvestHealthResponse = {
  sources: SourceHealthEntry[];
  status: string;
};

export type SourceHealthEntry = {
  id: string;
  name: string;
  tier: string;
  active: boolean;
  eligible: number;
  total: number;
  status?: string;
};

export type QualificationSummaryResponse = {
  manualGovernanceOnly: boolean;
  reviewReadyRequired: boolean;
  proofCaptureRequired: boolean;
};

export type { DashboardTelemetry };
