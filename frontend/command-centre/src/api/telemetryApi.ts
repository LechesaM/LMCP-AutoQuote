import { fetchDashboardTelemetry } from "./dashboardTelemetryClient";
import { normalizeDashboardTelemetry } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchTelemetrySnapshot() {
  const telemetry = await fetchDashboardTelemetry();
  const state = useTelemetryStore.getState();
  return {
    commandMetrics: telemetry,
    opportunityBreakdown: state.opportunityBreakdown,
    provinceDistribution: state.provinceDistribution,
    recentAlerts: state.recentAlerts,
    topHighProfitRfqs: state.topHighProfitRfqs,
  };
}

export async function fetchTelemetryMetrics() {
  const telemetry = await fetchDashboardTelemetry();
  return normalizeDashboardTelemetry(telemetry);
}
