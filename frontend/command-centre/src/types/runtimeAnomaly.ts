export type RuntimeAnomaly = {
  anomalyId: string;
  type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  affectedSystems: string[];
  evidence: Record<string, any>;
  createdAt: string;
  advisoryOnly: boolean;
};

export type RuntimeAnomalySnapshot = {
  status: string;
  generatedAt: string;
  dataSource: string;
  anomalies: RuntimeAnomaly[];
  anomalyCount: number;
  severityCounts: Record<string, number>;
  advisoryOnly: boolean;
};
