export type IncidentRecord = {
  incidentId: string
  incidentType: string
  title: string
  severity: string
  status: string
  operatorId: string
  createdAt: string
  updatedAt: string
  acknowledgedAt: string
  acknowledgedBy: string
  details: Record<string, unknown>
}

