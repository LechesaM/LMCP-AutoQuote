import { fetchDashboardTelemetry } from "./dashboardTelemetryClient";
import { normalizeDashboardTelemetry } from "./normalize";

export async function fetchTelemetrySnapshot() {
  const telemetry = await fetchDashboardTelemetry();
  return {
    commandMetrics: telemetry.commandMetrics,
    opportunityBreakdown: telemetry.opportunityBreakdown,
    provinceDistribution: telemetry.provinceDistribution,
    recentAlerts: telemetry.recentAlerts,
    topHighProfitRfqs: telemetry.topHighProfitRfqs,
    generatedAt: telemetry.generatedAt,
    dataSource: telemetry.dataSource,
    status: telemetry.status,
  };
}

export async function fetchTelemetryMetrics() {
  const telemetry = await fetchDashboardTelemetry();
  return normalizeDashboardTelemetry(telemetry).commandMetrics;
}
