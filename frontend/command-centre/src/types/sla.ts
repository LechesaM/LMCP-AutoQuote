export type SlaMetric = {
  name: string;
  value: number;
  state: "healthy" | "degraded" | "failing";
};

export type SlaMonitoringSnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  slaMetrics: SlaMetric[];
  breachedMetrics: SlaMetric[];
  warningMetrics: SlaMetric[];
  summary: {
    healthy: number;
    degraded: number;
    failing: number;
  };
};
