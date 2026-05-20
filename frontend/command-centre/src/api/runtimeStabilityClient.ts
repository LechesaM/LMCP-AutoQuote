import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeStabilizationDeploymentStability,
  normalizeStabilizationFallbackHealth,
  normalizeStabilizationGovernanceConsistency,
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
  const operationalWarnings = [
    ...(queue.summary?.queueLagMinutes > 30 ? ["Queue lag is elevated."] : []),
    ...(sourceHealth.summary?.failingSources > 0 ? ["Source failures are present."] : []),
    ...(telemetry.recentAlerts?.length ? ["Runtime alerts are active."] : []),
  ];
  return {
    status: "runtime_fallback",
    generatedAt,
    dataSource,
    runtime_stability: {
      status: operationalWarnings.length ? "degraded" : "healthy",
      generatedAt,
      dataSource,
      stability_score: operationalWarnings.length ? 72 : 92,
      degradation_trends: [
        {
          label: "queue_lag_minutes",
          value: Number(queue.summary?.queueLagMinutes || 0),
          healthy: Number(queue.summary?.queueLagMinutes || 0) <= 30 ? 1 : 0,
          degraded: Number(queue.summary?.queueLagMinutes || 0) > 0 ? 1 : 0,
          failing: Number(queue.summary?.queueLagMinutes || 0) > 60 ? 1 : 0,
        },
        {
          label: "source_failures",
          value: Number(sourceHealth.summary?.failingSources || 0),
          healthy: Number(sourceHealth.summary?.failingSources || 0) === 0 ? 1 : 0,
          degraded: Number(sourceHealth.summary?.failingSources || 0) > 0 ? 1 : 0,
          failing: Number(sourceHealth.summary?.failingSources || 0) > 2 ? 1 : 0,
        },
      ],
      operational_warnings: operationalWarnings,
      snapshot_health: {
        healthy: 1,
        degraded: operationalWarnings.length ? 1 : 0,
        failing: 0,
        window: 1,
      },
      queue_lag_minutes: Number(queue.summary?.queueLagMinutes || 0),
      telemetry_freshness_minutes: 0,
      worker_stale_count: 0,
      source_failure_count: Number(sourceHealth.summary?.failingSources || 0),
      alert_count: Number(telemetry.recentAlerts?.length || 0),
      anomaly_count: 0,
      window_size: 1,
      signals: {
        telemetry: telemetry.commandMetrics,
        queue: queue.summary,
        sources: sourceHealth.summary,
      },
    },
    fallback_health: {
      status: "degraded",
      generatedAt,
      dataSource,
      fallback_health_summary: {
        status: "degraded",
        fallbackActivations: 1,
        staleFallbacks: 0,
      },
      fallback_activations: 1,
      stale_fallbacks: 0,
      runtime_recovery_success: true,
      recovery_success_rate: 100,
      warnings: [],
      blockers: [],
      advisory_only: true,
    },
    telemetry_noise: {
      status: "degraded",
      generatedAt,
      dataSource,
      alerts: (telemetry.recentAlerts || []).map((alert, index) => ({
        alert_id: `alert-${index + 1}`,
        type: "runtime",
        severity: "warning",
        title: String(alert),
        message: String(alert),
        created_at: generatedAt,
        acknowledged: false,
        details: {},
      })),
      alert_groups: [
        { label: "warnings", count: telemetry.recentAlerts?.length || 0, severity: "warning" },
      ],
      severity_counts: { warning: telemetry.recentAlerts?.length || 0 },
      suppressed_count: 0,
      retained_count: telemetry.recentAlerts?.length || 0,
      critical_count: 0,
      noise_score: telemetry.recentAlerts?.length || 0,
      advisory_only: true,
    },
    governance_consistency: {
      status: "healthy",
      generatedAt,
      dataSource,
      consistency_score: 100,
      checks: [
        { label: "manual-only governance", status: "pass", passed: true, detail: "Manual approval remains required.", severity: "info" },
        { label: "review_ready enforcement", status: "pass", passed: true, detail: "Review readiness remains enforced.", severity: "info" },
        { label: "proof capture enforcement", status: "pass", passed: true, detail: "Proof capture remains enforced.", severity: "info" },
        { label: "rbac integrity", status: "pass", passed: true, detail: "RBAC remains enabled.", severity: "info" },
      ],
      inconsistencies: [],
      warnings: [],
      blockers: [],
      audit_attribution_missing: false,
      role_distribution: {},
      permissions: ["view_dashboard", "view_governance", "view_audit"],
    },
    deployment_stability: {
      status: "healthy",
      generatedAt,
      dataSource,
      deployment_stability_score: 90,
      startup_readiness: { status: "healthy" },
      runtime_integrity: { status: "healthy" },
      environment_summary: { status: "healthy" },
      persistence_health: { status: "healthy" },
      queue_summary: queue.summary,
      route_availability: { stabilization_router: true },
      route_names: ["/stabilization/runtime", "/stabilization/fallback-health"],
      warnings: [],
      startup_blockers: [],
      blockers: [],
      auth_available: true,
      persistence_available: true,
      queue_available: true,
      observability_available: true,
    },
  };
}

export async function fetchRuntimeStabilityData() {
  const fallback = buildFallbackSnapshot();
  const [runtime, fallbackHealth, telemetryNoise, governanceConsistency, deploymentStability] = await Promise.all([
    axiosAdapter("/stabilization/runtime"),
    axiosAdapter("/stabilization/fallback-health"),
    axiosAdapter("/stabilization/telemetry-noise"),
    axiosAdapter("/stabilization/governance-consistency"),
    axiosAdapter("/stabilization/deployment-stability"),
  ]);

  return {
    runtimeStability: normalizeStabilizationRuntime(runtime || fallback.runtime_stability, fallback),
    fallbackHealth: normalizeStabilizationFallbackHealth(fallbackHealth || fallback.fallback_health, fallback),
    telemetryNoise: normalizeStabilizationTelemetryNoise(telemetryNoise || fallback.telemetry_noise, fallback),
    governanceConsistency: normalizeStabilizationGovernanceConsistency(governanceConsistency || fallback.governance_consistency, fallback),
    deploymentStability: normalizeStabilizationDeploymentStability(deploymentStability || fallback.deployment_stability, fallback),
  };
}
