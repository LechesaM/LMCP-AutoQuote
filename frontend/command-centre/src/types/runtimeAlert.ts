export type RuntimeAlertRecord = {
  alertId: string
  type: string
  severity: string
  title: string
  message: string
  createdAt: string
  acknowledged: boolean
  details: Record<string, unknown>
}

