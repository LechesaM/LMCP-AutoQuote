import { axiosAdapter } from "./axiosAdapter";
import { fetchDashboardTelemetry } from "./dashboardTelemetryClient";
import { fetchOperationalAnalyticsData } from "./operationalAnalyticsClient";
import { normalizeForecastingAnalytics } from "./normalize";

function buildFallbackSnapshot(dashboard, operational) {
  return {
    status: "runtime_fallback",
    generated_at: dashboard?.generatedAt || operational?.generatedAt || new Date().toISOString(),
    data_source: dashboard?.dataSource || operational?.dataSource || "runtime_fallback",
    summary: {
      queue_growth: Number(operational?.runtimeMetrics?.queueLag || 0),
      operator_workload: Number(operational?.runtimeMetrics?.operatorUtilization || 0),
      rfq_throughput: Number(operational?.runtimeMetrics?.reviewThroughput || 0),
      source_growth: Number(dashboard?.commandMetrics?.totalHarvested || 0),
      estimated_review_demand: Number(dashboard?.eligibleRfqs || 0),
      rfq_growth: Number(dashboard?.commandMetrics?.totalHarvested || 0),
      review_demand: Number(dashboard?.eligibleRfqs || 0),
      opportunity_value_projection: Number(dashboard?.estimatedValue || 0),
    },
    forecast: {
      trends: {},
      projections: {},
    },
    advisory_only: true,
    estimated: true,
    non_financial_advice: true,
    heuristic: true,
  };
}

export async function fetchForecastingAnalytics() {
  const remote = await axiosAdapter("/business/workload-forecast");
  const opportunity = await axiosAdapter("/business/opportunity-forecast");
  const revenue = await axiosAdapter("/business/revenue-projection");
  if (remote || opportunity || revenue) {
    return normalizeForecastingAnalytics({
      workload_forecast: remote || {},
      opportunity_forecast: opportunity || {},
      revenue_projection: revenue || {},
    });
  }
  const [dashboard, operational] = await Promise.all([
    fetchDashboardTelemetry().catch(() => null),
    fetchOperationalAnalyticsData().catch(() => null),
  ]);
  return normalizeForecastingAnalytics(buildFallbackSnapshot(dashboard, operational));
}

