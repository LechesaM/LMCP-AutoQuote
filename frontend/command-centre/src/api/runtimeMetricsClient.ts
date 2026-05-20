import { axiosAdapter } from "./axiosAdapter";
import { normalizeBackupValidation, normalizeRuntimeMetrics } from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchRuntimeMetricsData() {
  const remote = await axiosAdapter("/operations/runtime-metrics");
  const fallback = {
    status: "runtime_fallback",
    generatedAt: useTelemetryStore.getState().lastRefreshedAt,
    dataSource: useTelemetryStore.getState().dataSource,
    metrics: {
      rfqsHarvestedPerHour: Number(useTelemetryStore.getState().commandMetrics?.totalHarvested || 0),
      reviewThroughput: Number(useQueueStore.getState().summary?.approvedToday || 0),
      queueLag: Number(useQueueStore.getState().summary?.queueLagMinutes || 0),
      operatorUtilization: Number(useQueueStore.getState().summary?.operatorCapacityUsed || 0) / 10,
      parserFailureRate: Number(useSourceHealthStore.getState().summary?.parserFailureRate || 0),
      sourceAvailability: Number(useSourceHealthStore.getState().summary?.healthySources || 0),
      telemetryFreshnessMinutes: 0,
      workflowFailures: 0,
      persistenceFailures: 0,
      authFailures: 0,
      rateLimitEvents: 0,
      apiLatencyMs: 0,
    },
    systemHealth: {},
    operatorCapacity: useQueueStore.getState().summary || {},
    queueSummary: useQueueStore.getState().summary || {},
    sourceSummary: useSourceHealthStore.getState().summary || {},
    workflowSummary: {},
    persistence: {},
  };
  return normalizeRuntimeMetrics(remote || fallback, fallback);
}

export async function fetchBackupValidationData() {
  const remote = await axiosAdapter("/operations/backup-validation");
  return normalizeBackupValidation(remote || {}, {
    status: "runtime_fallback",
    generatedAt: new Date().toISOString(),
    dataSource: "static_seed",
    backupCount: 0,
    backupDir: "",
    latestBackup: "",
    latestBackupVerified: false,
    latestBackupAgeDays: -1,
    auditPersistenceOk: false,
    restoreSimulation: { status: "warning", non_destructive: true, validation_only: true },
  });
}
