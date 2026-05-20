import { axiosAdapter } from "./axiosAdapter";
import { normalizeRuntimeMetrics } from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchOperationalAnalyticsData() {
  const [operatorAnalytics, sourceReliability, runtimeMetrics] = await Promise.all([
    axiosAdapter("/operations/operator-analytics"),
    axiosAdapter("/operations/source-reliability"),
    axiosAdapter("/operations/runtime-metrics"),
  ]);

  return {
    status: operatorAnalytics?.status || sourceReliability?.status || runtimeMetrics?.status || "runtime_fallback",
    generatedAt: operatorAnalytics?.generated_at || sourceReliability?.generated_at || runtimeMetrics?.generated_at || new Date().toISOString(),
    dataSource: operatorAnalytics?.data_source || sourceReliability?.data_source || runtimeMetrics?.data_source || "runtime_fallback",
    operatorAnalytics: operatorAnalytics || {},
    sourceReliability: sourceReliability || {},
    runtimeMetrics: normalizeRuntimeMetrics(runtimeMetrics || {}, {
      status: "runtime_fallback",
      generatedAt: useTelemetryStore.getState().lastRefreshedAt,
      dataSource: "static_seed",
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
      persistence: {},
    }),
  };
}

