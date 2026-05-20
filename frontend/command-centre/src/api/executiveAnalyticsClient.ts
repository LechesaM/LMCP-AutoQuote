import { axiosAdapter } from "./axiosAdapter";
import { fetchDashboardTelemetry } from "./dashboardTelemetryClient";
import { fetchOperationalAnalyticsData } from "./operationalAnalyticsClient";
import { normalizeExecutiveAnalytics } from "./normalize";

function buildFallbackSnapshot(dashboard, operational) {
  return {
    status: "runtime_fallback",
    generated_at: dashboard?.generatedAt || operational?.generatedAt || new Date().toISOString(),
    data_source: dashboard?.dataSource || operational?.dataSource || "runtime_fallback",
    executive_summary: {
      rfqs_harvested: Number(dashboard?.commandMetrics?.totalHarvested || 0),
      rfqs_qualified: Number(dashboard?.commandMetrics?.eligibleRfqs || 0),
      rfqs_reviewed: Number(operational?.runtimeMetrics?.reviewThroughput || 0),
      go_trend: Number(dashboard?.commandMetrics?.highProfitRfqs || 0),
      manual_review_trend: Number(dashboard?.eligibleRfqs || 0),
      reject_trend: Number(operational?.runtimeMetrics?.workflowFailures || 0),
      estimated_profitability: Number(dashboard?.estimatedValue || 0),
      operator_throughput: Number(operational?.operatorAnalytics?.summary?.average_reviews_per_operator || 0),
      queue_pressure: Number(operational?.runtimeMetrics?.queueLag || 0),
      governance_incidents: Number(operational?.runtimeMetrics?.workflowFailures || 0) + Number(operational?.runtimeMetrics?.persistenceFailures || 0),
      source_reliability: Number(operational?.sourceReliability?.summary?.harvest_success_rate || 0) * 100,
      sla_health: "degraded",
      qualified_rate: Number(dashboard?.eligibleRate || 0),
      manual_governance_integrity_score: 0,
      operational_reliability_score: 0,
      quality_score: 0,
    },
    weekly_trend: [],
    monthly_trend: [],
    rolling_averages: { weekly_total: [], monthly_total: [] },
    profitability: {},
    rfq_conversion: {},
    source_roi: {},
    operator_trends: {},
    governance_trends: {},
    workload_forecast: {},
    opportunity_forecast: {},
    revenue_projection: {},
    historical_trends: {},
    productivity: {},
    source_reliability: {},
    sla: {},
    runtime_metrics: operational?.runtimeMetrics || {},
    workflow_summary: operational?.operatorAnalytics || {},
    pilot_readiness: {},
    tender_success_analytics: {},
    observability_summary: {},
    strategic_highlights: ["Fallback executive analytics are advisory only."],
  };
}

export async function fetchExecutiveAnalytics() {
  const remote = await axiosAdapter("/business/executive-summary");
  if (remote) {
    return normalizeExecutiveAnalytics(remote);
  }
  const [dashboard, operational] = await Promise.all([
    fetchDashboardTelemetry().catch(() => null),
    fetchOperationalAnalyticsData().catch(() => null),
  ]);
  return normalizeExecutiveAnalytics(buildFallbackSnapshot(dashboard, operational));
}

