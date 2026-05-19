import { useMemo } from "react";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

export function useOperationalHealth() {
  const sources = useSourceHealthStore((state) => state.sources);
  const queueSummary = useQueueStore((state) => state.summary);
  const commandMetrics = useTelemetryStore((state) => state.commandMetrics);
  const recentAlerts = useTelemetryStore((state) => state.recentAlerts);
  const telemetryUpdatedAt = useTelemetryStore((state) => state.lastRefreshedAt);

  return useMemo(() => {
    const sourceFailures = sources.filter((source) => source.status !== "healthy").length;
    const parserFailures = sources.filter((source) => Number(source.parserFailureRate || 0) > 0.1).length;
    const staleEvidence = sources.filter((source) => Boolean(source.evidenceStale)).length;
    const queueLag = Number(queueSummary.lagItems || 0);
    const operatorCapacityTotal = 1000;
    const operatorCapacityUsed = Number(queueSummary.total || 0);
    const operatorCapacityRemaining = Math.max(0, operatorCapacityTotal - operatorCapacityUsed);
    const operatorCapacityUtilization = operatorCapacityTotal
      ? Math.round((operatorCapacityUsed / operatorCapacityTotal) * 1000) / 10
      : 0;
    const rfqAging = Math.max(0, Number(commandMetrics.totalHarvested || 0) - Number(commandMetrics.eligibleRfqs || 0));
    const staleEvidenceSignals = staleEvidence + recentAlerts.filter((alert) => /update|soon|within 2 days|stale/i.test(String(alert))).length;
    const severity =
      sourceFailures > 0 || parserFailures > 0
        ? "stale"
        : queueLag > 0 || staleEvidenceSignals > 0
          ? "refreshing"
          : "ready";

    return {
      state: severity,
      sourceFailures,
      parserFailures,
      queueLag,
      operatorCapacity: {
        total: operatorCapacityTotal,
        used: operatorCapacityUsed,
        remaining: operatorCapacityRemaining,
        utilization: operatorCapacityUtilization,
      },
      rfqAging,
      staleEvidence: staleEvidenceSignals,
      queueLagLabel: queueLag > 0 ? "Backlog present" : "No lag detected",
      telemetryUpdatedAt,
      queueUpdatedAt: queueSummary.lastRefreshedAt || "",
      sourceHealthUpdatedAt: sources[0]?.lastUpdatedAt || "",
    };
  }, [sources, queueSummary, commandMetrics, recentAlerts, telemetryUpdatedAt]);
}
