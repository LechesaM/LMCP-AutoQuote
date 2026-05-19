export type PricingEvidenceRow = {
  tenderId: string;
  title: string;
  supplierEvidenceScore: number;
  pricingDefensibilityScore: number;
  pricingConfidence: number;
  quoteAgeDays: number;
  riskLevel: string;
  operatorOverrideNotes: string;
  traceabilityChain: Array<Record<string, unknown> | string>;
};

export type PricingEvidenceResponse = {
  status: string;
  generatedAt: string;
  dataSource: string;
  summary: {
    supplier_quote_completeness_average: number;
    pricing_defensibility_average: number;
    pricing_confidence_average: number;
    stale_quote_count: number;
    vat_mismatch_count: number;
    subtotal_mismatch_count: number;
    delivery_inconsistency_count: number;
  };
  pricingEvidenceRows: PricingEvidenceRow[];
  pricingAnomalies: Array<{ name: string; count: number }>;
};
