export type RuntimeMetricsData = {
  status: string
  generatedAt: string
  dataSource: string
  metrics: {
    rfqsHarvestedPerHour: number
    reviewThroughput: number
    queueLag: number
    operatorUtilization: number
    parserFailureRate: number
    sourceAvailability: number
    telemetryFreshnessMinutes: number
    workflowFailures: number
    persistenceFailures: number
    authFailures: number
    rateLimitEvents: number
    apiLatencyMs: number
  }
  systemHealth: Record<string, unknown>
  operatorCapacity: Record<string, unknown>
  queueSummary: Record<string, unknown>
  sourceSummary: Record<string, unknown>
  workflowSummary: Record<string, unknown>
  persistence: Record<string, unknown>
}

export type RuntimeAlert = {
  alertId: string
  type: string
  severity: "info" | "warning" | "critical" | string
  title: string
  message: string
  createdAt: string
  acknowledged: boolean
  details: Record<string, unknown>
}

export type IncidentRecord = {
  incidentId: string
  incidentType: string
  title: string
  severity: "info" | "warning" | "critical" | string
  status: string
  operatorId: string
  createdAt: string
  updatedAt: string
  acknowledgedAt: string
  acknowledgedBy: string
  details: Record<string, unknown>
}
