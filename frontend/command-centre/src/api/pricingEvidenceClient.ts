import { axiosAdapter } from "./axiosAdapter";
import { normalizePricingEvidence } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchPricingEvidence() {
  const remote = await axiosAdapter("/operations/pricing-evidence");
  if (remote?.pricingEvidenceRows) {
    return normalizePricingEvidence(remote);
  }
  const telemetry = useTelemetryStore.getState();
  const rows = telemetry.topHighProfitRfqs.map((item, index) => ({
    tenderId: `fallback-p-${index + 1}`,
    title: item.title,
    supplierEvidenceScore: 58,
    pricingDefensibilityScore: 55,
    pricingConfidence: 62,
    quoteAgeDays: index + 2,
    riskLevel: index === 0 ? "low" : "medium",
    operatorOverrideNotes: "",
    traceabilityChain: [{ source: "fallback", title: item.title }],
  }));
  return normalizePricingEvidence({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || new Date().toISOString(),
    dataSource: telemetry.dataSource || "static_seed",
    summary: {
      supplier_quote_completeness_average: 58,
      pricing_defensibility_average: 55,
      pricing_confidence_average: 62,
      stale_quote_count: 0,
      vat_mismatch_count: 0,
      subtotal_mismatch_count: 0,
      delivery_inconsistency_count: 0,
    },
    pricingEvidenceRows: rows,
    pricingAnomalies: [],
  });
}
