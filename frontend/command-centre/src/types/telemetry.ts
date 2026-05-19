export type TelemetrySummary = {
  totalHarvested: number;
  eligibleRfqs: number;
  estimatedValue: number;
  highProfitRfqs: number;
  avgEstimatedProfit: number;
  avgMargin: number;
  eligibleRate: number;
};

export interface DashboardTelemetry {
  totalHarvested: number;
  eligibleRfqs: number;
  estimatedValue: number;
  avgMargin: number;
  highProfitRfqs?: number;
  avgEstimatedProfit?: number;
  eligibleRate?: number;
}

export type ProvinceTelemetry = {
  code: string;
  province: string;
  rfqs: number;
  eligible: number;
  value: number;
  avgMargin: number;
};
