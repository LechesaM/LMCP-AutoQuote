import { axiosAdapter } from "./axiosAdapter";
import { normalizeOperationalHealth } from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchOperationalHealthData() {
  const remote = await axiosAdapter("/telemetry/operational-health");
  const fallback = {
    status: "runtime_fallback",
    generatedAt: new Date().toISOString(),
    dataSource: "static_seed",
    sourceFailures: useSourceHealthStore.getState().sources.filter((item) => item.status !== "healthy").length,
    parserFailures: useSourceHealthStore.getState().sources.filter((item) => Number(item.parserFailureRate || 0) > 0.1).length,
    queueLag: Number(useQueueStore.getState().summary?.lagItems || 0),
    operatorCapacity: 1000,
    rfqAging: Math.max(0, Number(useTelemetryStore.getState().commandMetrics.totalHarvested || 0) - Number(useTelemetryStore.getState().commandMetrics.eligibleRfqs || 0)),
    staleEvidence: useSourceHealthStore.getState().sources.filter((item) => Boolean(item.evidenceStale)).length,
    workflowFailures: 0,
    persistenceFailures: 0,
    auditFailures: 0,
    governanceComplianceScore: 0,
    manualGovernanceIntegrityScore: 0,
  };

  if (remote) {
    return normalizeOperationalHealth(remote, fallback);
  }
  return normalizeOperationalHealth(fallback, fallback);
}
