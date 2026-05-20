import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeRuntimeReliability,
  normalizeStabilizationDeploymentStability,
  normalizeStabilizationFallbackHealth,
  normalizeStabilizationRuntime,
  normalizeStabilizationTelemetryNoise,
} from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

const nowIso = () => new Date().toISOString();

function buildFallbackSnapshot() {
  const telemetry = useTelemetryStore.getState();
  const queue = useQueueStore.getState();
  const sourceHealth = useSourceHealthStore.getState();
  const generatedAt = nowIso();
  const dataSource = telemetry.dataSource || queue.dataSource || sourceHealth.dataSource || "static_seed";
  return {
    status: "runtime_fallback",
    generatedAt,
    dataSource,
    runtimeStability: {
      status: "degraded",
      generatedAt,
      dataSource,
      stabilityScore: 70,
      degradationTrends: [
        { label: "queue_lag", value: Number(queue.summary?.queueLagMinutes || 0), healthy: 0, degraded: 1, failing: 0 },
      ],
      operationalWarnings: queue.summary?.queueLagMinutes > 0 ? ["Queue lag remains elevated."] : [],
      snapshotHealth: { healthy: 1, degraded: queue.summary?.queueLagMinutes > 0 ? 1 : 0, failing: 0, window: 1 },
      queueLagMinutes: Number(queue.summary?.queueLagMinutes || 0),
      telemetryFreshnessMinutes: 0,
      workerStaleCount: 0,
      sourceFailureCount: Number(sourceHealth.summary?.failingSources || 0),
      alertCount: Number(telemetry.recentAlerts?.length || 0),
      anomalyCount: 0,
      windowSize: 1,
      signals: { telemetry: telemetry.commandMetrics, queue: queue.summary, sources: sourceHealth.summary },
    },
    fallbackHealth: {
      status: "degraded",
      generatedAt,
      dataSource,
      fallbackHealthSummary: { status: "degraded" },
      fallbackActivations: 1,
      staleFallbacks: 0,
      runtimeRecoverySuccess: true,
      recoverySuccessRate: 100,
      warnings: [],
      blockers: [],
      advisoryOnly: true,
    },
    telemetryNoise: {
      status: "degraded",
      generatedAt,
      dataSource,
      alerts: [],
      alertGroups: [],
      severityCounts: {},
      suppressedCount: 0,
      retainedCount: 0,
      criticalCount: 0,
      noiseScore: 0,
      advisoryOnly: true,
    },
    deploymentStability: {
      status: "healthy",
      generatedAt,
      dataSource,
      deploymentStabilityScore: 90,
      startupReadiness: { status: "healthy" },
      runtimeIntegrity: { status: "healthy" },
      environmentSummary: { status: "healthy" },
      persistenceHealth: { status: "healthy" },
      queueSummary: queue.summary,
      routeAvailability: { stabilization_router: true },
      routeNames: ["/stabilization/runtime"],
      warnings: [],
      startupBlockers: [],
      blockers: [],
      authAvailable: true,
      persistenceAvailable: true,
      queueAvailable: true,
      observabilityAvailable: true,
    },
  };
}

export async function fetchRuntimeReliabilityData() {
  const fallback = buildFallbackSnapshot();
  const [runtime, fallbackHealth, telemetryNoise, deploymentStability] = await Promise.all([
    axiosAdapter("/stabilization/runtime"),
    axiosAdapter("/stabilization/fallback-health"),
    axiosAdapter("/stabilization/telemetry-noise"),
    axiosAdapter("/stabilization/deployment-stability"),
  ]);

  const snapshot = {
    runtimeStability: normalizeStabilizationRuntime(runtime || fallback.runtimeStability, fallback),
    fallbackHealth: normalizeStabilizationFallbackHealth(fallbackHealth || fallback.fallbackHealth, fallback),
    telemetryNoise: normalizeStabilizationTelemetryNoise(telemetryNoise || fallback.telemetryNoise, fallback),
    deploymentStability: normalizeStabilizationDeploymentStability(deploymentStability || fallback.deploymentStability, fallback),
  };

  return normalizeRuntimeReliability(snapshot, {
    status: snapshot.runtimeStability.status,
    generatedAt: snapshot.runtimeStability.generatedAt,
    dataSource: snapshot.runtimeStability.dataSource,
    runtimeStability: snapshot.runtimeStability,
    fallbackHealth: snapshot.fallbackHealth,
    telemetryNoise: snapshot.telemetryNoise,
    deploymentStability: snapshot.deploymentStability,
  });
}
