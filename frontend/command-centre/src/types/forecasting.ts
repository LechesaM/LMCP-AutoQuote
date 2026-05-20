export type ForecastingSnapshot = {
  status: string
  generatedAt: string
  dataSource: string
  summary: {
    queueGrowth?: number
    operatorWorkload?: number
    rfqThroughput?: number
    sourceGrowth?: number
    estimatedReviewDemand?: number
    rfqGrowth?: number
    reviewDemand?: number
    opportunityValueProjection?: number
  }
  forecast: Record<string, any>
  advisoryOnly: boolean
  estimated?: boolean
  nonFinancialAdvice?: boolean
  heuristic?: boolean
}

