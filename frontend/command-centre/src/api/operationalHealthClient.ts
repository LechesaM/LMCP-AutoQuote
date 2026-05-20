import { axiosAdapter } from "./axiosAdapter";
import { normalizeOperationalHealth } from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";
import { commandMetrics } from "../data/harvestedRfqs";

const STABLE_OPERATIONAL_FALLBACK = normalizeOperationalHealth(
  {
    status: "runtime_fallback",
    generated_at: "static_seed",
    data_source: "static_seed",
    source_failures: 0,
    parser_failures: 0,
    queue_lag: 0,
    operator_capacity: 1000,
    rfq_aging: Math.max(0, Number(commandMetrics.totalHarvested || 0) - Number(commandMetrics.eligibleRfqs || 0)),
    stale_evidence: 0,
    workflow_failures: 0,
    persistence_failures: 0,
    audit_failures: 0,
    governance_compliance_score: 0,
    manual_governance_integrity_score: 0,
  },
  {
    status: "runtime_fallback",
    generatedAt: "static_seed",
    dataSource: "static_seed",
    sourceFailures: 0,
    parserFailures: 0,
    queueLag: 0,
    operatorCapacity: 1000,
    rfqAging: Math.max(0, Number(commandMetrics.totalHarvested || 0) - Number(commandMetrics.eligibleRfqs || 0)),
    staleEvidence: 0,
    workflowFailures: 0,
    persistenceFailures: 0,
    auditFailures: 0,
    governanceComplianceScore: 0,
    manualGovernanceIntegrityScore: 0,
  },
);

export async function fetchOperationalHealthData() {
  const remote = await axiosAdapter("/telemetry/operational-health");
  if (remote) {
    const fallback = {
      ...STABLE_OPERATIONAL_FALLBACK,
      sourceFailures: useSourceHealthStore.getState().sources.filter((item) => item.status !== "healthy").length,
      parserFailures: useSourceHealthStore.getState().sources.filter((item) => Number(item.parserFailureRate || 0) > 0.1).length,
      queueLag: Number(useQueueStore.getState().summary?.lagItems || 0),
      staleEvidence: useSourceHealthStore.getState().sources.filter((item) => Boolean(item.evidenceStale)).length,
      rfqAging: Math.max(0, Number(useTelemetryStore.getState().commandMetrics.totalHarvested || 0) - Number(useTelemetryStore.getState().commandMetrics.eligibleRfqs || 0)),
    };
    return normalizeOperationalHealth(remote, fallback);
  }
  return STABLE_OPERATIONAL_FALLBACK;
}
