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
  status?: string;
  generatedAt?: string;
  dataSource?: string;
  commandMetrics: TelemetrySummary;
  provinceDistribution: ProvinceTelemetry[];
  opportunityBreakdown: OpportunityBreakdownItem[];
  topHighProfitRfqs: HighProfitRfq[];
  recentAlerts: string[];
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

export type OpportunityBreakdownItem = {
  name: string;
  value: number;
};

export type HighProfitRfq = {
  title: string;
  province: string;
  value: string;
  profit: string;
};
