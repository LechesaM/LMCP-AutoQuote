import { axiosAdapter } from "./axiosAdapter";
import { fetchDashboardTelemetry } from "./dashboardTelemetryClient";
import { normalizeProfitabilityAnalytics } from "./normalize";

function buildFallbackSnapshot(dashboard) {
  return {
    status: "runtime_fallback",
    generated_at: dashboard?.generatedAt || new Date().toISOString(),
    data_source: dashboard?.dataSource || "runtime_fallback",
    summary: {
      estimated_total_profit: Number(dashboard?.estimatedValue || 0) * 0.25,
      average_estimated_profit: Number(dashboard?.avgEstimatedProfit || 0),
      average_margin: Number(dashboard?.avgMargin || 0),
      high_value_rfq_count: Number(dashboard?.highProfitRfqs || 0),
      low_confidence_profitability_count: 0,
      stale_pricing_impact_count: 0,
      supplier_evidence_impact_average: 0,
    },
    estimated_rfq_profitability: [],
    estimated_margin_distribution: {},
    high_value_rfqs: [],
    low_confidence_profitability: [],
    stale_pricing_impact: [],
    supplier_evidence_impact: [],
    profitability_by_source: [],
    profitability_by_province: [],
  };
}

export async function fetchProfitabilityAnalytics() {
  const remote = await axiosAdapter("/business/profitability");
  if (remote) {
    return normalizeProfitabilityAnalytics(remote);
  }
  const dashboard = await fetchDashboardTelemetry().catch(() => null);
  return normalizeProfitabilityAnalytics(buildFallbackSnapshot(dashboard));
}

