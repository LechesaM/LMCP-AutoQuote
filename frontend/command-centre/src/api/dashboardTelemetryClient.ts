import { axiosAdapter } from "./axiosAdapter";
import { normalizeDashboardTelemetry } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";
import {
  commandMetrics,
  opportunityBreakdown,
  provinceDistribution,
  recentAlerts,
  topHighProfitRfqs,
} from "../data/harvestedRfqs";

const STABLE_DASHBOARD_FALLBACK = normalizeDashboardTelemetry(
  {
    status: "ok",
    generated_at: "static_seed",
    data_source: "static_seed",
    command_metrics: commandMetrics,
    province_distribution: provinceDistribution,
    opportunity_breakdown: opportunityBreakdown,
    top_high_profit_rfqs: topHighProfitRfqs,
    recent_alerts: recentAlerts,
  },
  {
    commandMetrics,
    provinceDistribution,
    opportunityBreakdown,
    topHighProfitRfqs,
    recentAlerts,
    dataSource: "static_seed",
    generatedAt: "static_seed",
  },
);

export async function fetchDashboardTelemetry() {
  const remote = await axiosAdapter("/telemetry/dashboard");
  if (remote) {
    return normalizeDashboardTelemetry(remote, useTelemetryStore.getState());
  }
  return STABLE_DASHBOARD_FALLBACK;
}
