export type ObservabilitySectionState = {
  status: string;
  generatedAt: string;
  dataSource: string;
  [key: string]: any;
};

export type ObservabilitySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  prometheus: ObservabilitySectionState;
  grafana: ObservabilitySectionState;
  sentry: ObservabilitySectionState;
  sla: ObservabilitySectionState;
  anomalies: ObservabilitySectionState;
  alerts: ObservabilitySectionState;
  logs: ObservabilitySectionState;
  uptime: ObservabilitySectionState;
  performance: ObservabilitySectionState;
  summary: Record<string, any>;
};
