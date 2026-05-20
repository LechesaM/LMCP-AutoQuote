import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeStabilizationFallbackHealth,
  normalizeStabilizationOperatorFatigue,
  normalizeStabilizationOperatorFeedback,
  normalizeStabilizationRuntimeCleanup,
} from "./normalize";
import useQueueStore from "../store/queueStore";
import useTelemetryStore from "../store/telemetryStore";

const nowIso = () => new Date().toISOString();

function buildFallbackSnapshot() {
  const telemetry = useTelemetryStore.getState();
  const queue = useQueueStore.getState();
  const generatedAt = nowIso();
  const dataSource = telemetry.dataSource || queue.dataSource || "static_seed";
  return {
    status: "runtime_fallback",
    generatedAt,
    dataSource,
    operator_fatigue: {
      status: "degraded",
      generatedAt,
      dataSource,
      fatigue_score: Number(queue.summary?.overdueReviews || 0) * 5,
      warnings: queue.summary?.overdueReviews ? ["Overdue reviews are present."] : [],
      fatigue_rows: [
        {
          operator_id: "unassigned",
          workload_score: Number(queue.summary?.operatorCapacityUsed || 0),
          fatigue_score: Number(queue.summary?.overdueReviews || 0) * 5,
          warning: queue.summary?.overdueReviews ? "Review backlog may cause fatigue." : "",
          recommendation: "rebalance_workload",
          overdue_reviews: Number(queue.summary?.overdueReviews || 0),
          repeated_escalations: 0,
          prolonged_queue_exposure: Number(queue.summary?.queueLagMinutes || 0),
          focus_session_exhaustion: 0,
        },
      ],
      workload_rebalance_recommendations: queue.summary?.overdueReviews ? ["Rebalance overdue reviews across the operator pool."] : [],
      signals: { queue: queue.summary, telemetry: telemetry.commandMetrics },
    },
    operator_feedback: {
      status: "degraded",
      generatedAt,
      dataSource,
      pain_points: queue.summary?.queueLagMinutes > 0 ? ["Queue lag increases review friction."] : [],
      trend_summary: {
        queueLagMinutes: queue.summary?.queueLagMinutes || 0,
        overdueReviews: queue.summary?.overdueReviews || 0,
      },
      feedback_items: [
        { label: "queue friction", value: queue.summary?.queueLagMinutes > 0 ? "elevated" : "stable" },
        { label: "evidence handling", value: "manual-review-controlled" },
      ],
      operational_signals: { queue: queue.summary },
    },
    runtime_cleanup: {
      status: "fallback",
      generatedAt,
      dataSource,
      dry_run_only: true,
      confirmed: false,
      cleanup_summary: { status: "dry-run", candidates: 0 },
      would_cleanup: [],
      warnings: [],
      blockers: [],
    },
    fallback_health: {
      status: "degraded",
      generatedAt,
      dataSource,
      fallback_health_summary: { status: "degraded" },
      fallback_activations: 1,
      stale_fallbacks: 0,
      runtime_recovery_success: true,
      recovery_success_rate: 100,
      warnings: [],
      blockers: [],
      advisory_only: true,
    },
  };
}

export async function fetchOperatorFeedbackData() {
  const fallback = buildFallbackSnapshot();
  const [fatigue, feedback, cleanup, fallbackHealth] = await Promise.all([
    axiosAdapter("/stabilization/operator-fatigue"),
    axiosAdapter("/stabilization/operator-feedback"),
    axiosAdapter("/stabilization/runtime-cleanup"),
    axiosAdapter("/stabilization/fallback-health"),
  ]);

  return {
    fatigue: normalizeStabilizationOperatorFatigue(fatigue || fallback.operator_fatigue, fallback),
    feedback: normalizeStabilizationOperatorFeedback(feedback || fallback.operator_feedback, fallback),
    cleanup: normalizeStabilizationRuntimeCleanup(cleanup || fallback.runtime_cleanup, fallback),
    fallbackHealth: normalizeStabilizationFallbackHealth(fallbackHealth || fallback.fallback_health, fallback),
  };
}
