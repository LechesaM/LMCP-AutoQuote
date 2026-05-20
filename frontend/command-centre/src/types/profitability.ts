export type ProfitabilityRow = {
  tenderId: string
  title: string
  estimatedProfit: number
  estimatedMargin: number
  province?: string
  source?: string
}

export type ProfitabilityAnalytics = {
  status: string
  generatedAt: string
  dataSource: string
  summary: {
    estimatedTotalProfit: number
    averageEstimatedProfit: number
    averageMargin: number
    highValueRfqCount: number
    lowConfidenceProfitabilityCount: number
    stalePricingImpactCount: number
    supplierEvidenceImpactAverage: number
  }
  estimatedRfqProfitability: ProfitabilityRow[]
  estimatedMarginDistribution: Record<string, number>
  highValueRfqs: ProfitabilityRow[]
  lowConfidenceProfitability: Array<{ tenderId: string; title: string; pricingConfidence: number }>
  stalePricingImpact: Array<{ tenderId: string; title: string }>
  supplierEvidenceImpact: Array<{ tenderId: string; supplierEvidenceScore: number }>
  profitabilityBySource: Array<{ source: string; estimatedProfit: number; count: number }>
  profitabilityByProvince: Array<{ province: string; estimatedProfit: number; count: number }>
}

