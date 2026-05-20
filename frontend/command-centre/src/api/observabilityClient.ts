import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeObservabilitySnapshot,
  normalizeSlaMonitoring,
  normalizeRuntimeAnomalies,
} from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

const nowIso = () => new Date().toISOString();

function buildFallbackObservabilitySnapshot() {
  const telemetry = useTelemetryStore.getState();
  const queue = useQueueStore.getState();
  const sourceHealth = useSourceHealthStore.getState();
  const generatedAt = nowIso();
  const dataSource = telemetry.dataSource || queue.dataSource || sourceHealth.dataSource || "static_seed";
  return {
    status: "runtime_fallback",
    generatedAt,
    dataSource,
    prometheus: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      metricsCount: 0,
      metrics: {},
      text: "",
    },
    grafana: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      dashboards: [],
      count: 0,
    },
    sentry: {
      status: "fallback",
      generatedAt,
      dataSource: "fallback",
      sentry: {
        enabled: false,
        dsnConfigured: false,
        environment: "",
        release: "",
        sampleRate: 0,
      },
    },
    sla: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      slaMetrics: [],
      breachedMetrics: [],
      warningMetrics: [],
      summary: { healthy: 0, degraded: 0, failing: 0 },
    },
    anomalies: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      anomalies: [],
      anomalyCount: 0,
      severityCounts: {},
      advisoryOnly: true,
    },
    alerts: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      alerts: [],
      routeCount: 0,
      categoryCounts: {},
      targetCounts: {},
      advisoryOnly: true,
    },
    logs: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      logs: {
        totalLogs: 0,
        logSources: {},
        categoryCounts: {},
        severityDistribution: {},
        redactedSamples: [],
      },
    },
    uptime: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      uptime: {
        status: "runtime_fallback",
        apiUptimePercentage: 0,
        observedWindowMinutes: 0,
        systemHealth: {},
        runtimeMetrics: {},
      },
    },
    performance: {
      status: "runtime_fallback",
      generatedAt,
      dataSource,
      performance: {
        status: "runtime_fallback",
        apiLatencyMs: 0,
        queueResponseTimeMs: 0,
        dbResponseHealth: "unknown",
        frontendBuildFreshnessMinutes: -1,
        deploymentHealth: "degraded",
        telemetryFreshnessMinutes: 0,
      },
    },
  };
}

export async function fetchObservabilitySnapshot() {
  const requests = await Promise.all([
    axiosAdapter("/observability/prometheus"),
    axiosAdapter("/observability/grafana"),
    axiosAdapter("/observability/sentry"),
    axiosAdapter("/observability/sla"),
    axiosAdapter("/observability/anomalies"),
    axiosAdapter("/observability/alerts"),
    axiosAdapter("/observability/logs"),
    axiosAdapter("/observability/uptime"),
    axiosAdapter("/observability/performance"),
  ]);
  const [prometheus, grafana, sentry, sla, anomalies, alerts, logs, uptime, performance] = requests;
  return normalizeObservabilitySnapshot(
    {
      prometheus: typeof prometheus === "string" ? { text: prometheus } : prometheus,
      grafana,
      sentry,
      sla,
      anomalies,
      alerts,
      logs,
      uptime,
      performance,
    },
    buildFallbackObservabilitySnapshot(),
  );
}

export async function fetchSlaMonitoringData() {
  const remote = await axiosAdapter("/observability/sla");
  return normalizeSlaMonitoring(remote || {}, buildFallbackObservabilitySnapshot().sla);
}

export async function fetchRuntimeAnomalyData() {
  const remote = await axiosAdapter("/observability/anomalies");
  return normalizeRuntimeAnomalies(remote || {}, buildFallbackObservabilitySnapshot().anomalies);
}
