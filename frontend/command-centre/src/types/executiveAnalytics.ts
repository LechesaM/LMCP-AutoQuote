export type ExecutiveTrendRow = {
  label: string
  count?: number
  total?: number
  go?: number
  manualReview?: number
  reject?: number
}

export type ExecutiveSummary = {
  rfqsHarvested: number
  rfqsQualified: number
  rfqsReviewed: number
  goTrend: number
  manualReviewTrend: number
  rejectTrend: number
  estimatedProfitability: number
  operatorThroughput: number
  queuePressure: number
  governanceIncidents: number
  sourceReliability: number
  slaHealth: string
  qualifiedRate: number
  manualGovernanceIntegrityScore: number
  operationalReliabilityScore: number
  qualityScore: number
}

export type ExecutiveAnalytics = {
  status: string
  generatedAt: string
  dataSource: string
  executiveSummary: ExecutiveSummary
  weeklyTrend: ExecutiveTrendRow[]
  monthlyTrend: ExecutiveTrendRow[]
  rollingAverages: {
    weeklyTotal: number[]
    monthlyTotal: number[]
  }
  profitability: Record<string, any>
  rfqConversion: Record<string, any>
  sourceROI: Record<string, any>
  operatorTrends: Record<string, any>
  governanceTrends: Record<string, any>
  workloadForecast: Record<string, any>
  opportunityForecast: Record<string, any>
  revenueProjection: Record<string, any>
  historicalTrends: Record<string, any>
  productivity: Record<string, any>
  sourceReliability: Record<string, any>
  sla: Record<string, any>
  runtimeMetrics: Record<string, any>
  workflowSummary: Record<string, any>
  pilotReadiness: Record<string, any>
  tenderSuccessAnalytics: Record<string, any>
  observabilitySummary: Record<string, any>
  strategicHighlights: string[]
}

