import useTelemetryStore from "../store/telemetryStore";

export function useTelemetry() {
  const commandMetrics = useTelemetryStore((state) => state.commandMetrics);
  const opportunityBreakdown = useTelemetryStore((state) => state.opportunityBreakdown);
  const provinceDistribution = useTelemetryStore((state) => state.provinceDistribution);
  const recentAlerts = useTelemetryStore((state) => state.recentAlerts);
  const topHighProfitRfqs = useTelemetryStore((state) => state.topHighProfitRfqs);

  return {
    commandMetrics,
    opportunityBreakdown,
    provinceDistribution,
    recentAlerts,
    topHighProfitRfqs,
  };
}
