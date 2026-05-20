import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeFocusSessions,
  normalizeOperatorShortcuts,
  normalizeOperatorWorkload,
  normalizeProductivitySnapshot,
  normalizeQueueHeatmap,
  normalizeReviewEfficiency,
  normalizeReviewPriorities,
  normalizeReviewQueueOptimization,
  normalizeEvidenceAcceleration,
} from "./normalize";
import useQueueStore from "../store/queueStore";
import useTelemetryStore from "../store/telemetryStore";
import { getReviewQueueItems } from "../store/reviewStore";

const nowIso = () => new Date().toISOString();

function buildFallbackProductivitySnapshot() {
  const queue = useQueueStore.getState();
  const telemetry = useTelemetryStore.getState();
  const reviewItems = queue.items?.length ? queue.items : getReviewQueueItems();
  const generatedAt = telemetry.lastRefreshedAt || nowIso();
  const operators = Array.from({ length: 10 }, (_, index) => {
    const assigned = reviewItems.filter((_, itemIndex) => itemIndex % 10 === index).length;
    const overdue = reviewItems.filter((_, itemIndex) => itemIndex % 4 === index % 4).length > 2 ? 1 : 0;
    const utilization = Math.min(100, Math.round((assigned / 100) * 1000) / 10);
    return {
      operatorId: `operator-${index + 1}`,
      assigned,
      overdue,
      utilization,
      timelineEvents: assigned * 2,
      specialization: index % 3 === 0 ? "general" : index % 3 === 1 ? "pricing" : "governance",
      workloadScore: assigned * 10 + overdue * 15,
      averageDueAgeHours: assigned ? round((assigned * 8) / 60, 2) : 0,
      priorityAverage: assigned ? round(65 - index * 2, 2) : 0,
    };
  });
  const queueOptimization = reviewItems.map((item, index) => ({
    tenderId: item.id,
    title: item.title,
    buyer: `Buyer ${index + 1}`,
    province: item.province,
    closingDate: generatedAt,
    workflowStage: "review_ready",
    reviewStatus: "pending",
    pricingConfidence: index === 0 ? 82 : 58,
    queueAgeMinutes: index * 18,
    priorityScore: index === 0 ? 96 : 72 - index,
    priorityGroup: index === 0 ? "urgent" : index < 3 ? "high" : index < 6 ? "medium" : "low",
    priorityReason: index === 0 ? "near closing date" : "queue age and evidence",
    riskLevel: index === 0 ? "high" : "medium",
    staleEvidence: index > 3,
    reviewReadiness: index === 0 ? "ready" : "manual",
    governanceBlocked: index > 4,
    submissionMethod: "email",
    sourceTier: "Tier 2",
    dataSource: telemetry.dataSource || "static_seed",
  }));
  const queueHeatmap = [
    { axis: "queue_age", label: "0-60", value: Math.min(6, reviewItems.length) },
    { axis: "queue_age", label: "60-240", value: Math.max(0, reviewItems.length - 3) },
    { axis: "queue_age", label: "240+", value: reviewItems.length > 8 ? 2 : 0 },
  ];
  return normalizeProductivitySnapshot(
    {
      status: "runtime_fallback",
      generated_at: generatedAt,
      data_source: telemetry.dataSource || "static_seed",
      workload: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        team_size: 10,
        total_daily_capacity: 1000,
        assigned_today: reviewItems.length,
        remaining_capacity: Math.max(0, 1000 - reviewItems.length),
        average_utilization: round((reviewItems.length / 1000) * 100, 2),
        average_workload_score: round(operators.reduce((sum, row) => sum + row.workloadScore, 0) / operators.length, 2),
        overload_warnings: reviewItems.length > 1000 ? ["Team capacity exceeded"] : [],
        underutilization_warnings: reviewItems.length < 20 ? ["Queue is lightly loaded"] : [],
        operators,
      },
      queueOptimization: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        optimized_queue: queueOptimization,
        priority_groups: {
          urgent: queueOptimization.filter((row) => row.priorityGroup === "urgent"),
          high: queueOptimization.filter((row) => row.priorityGroup === "high"),
          medium: queueOptimization.filter((row) => row.priorityGroup === "medium"),
          low: queueOptimization.filter((row) => row.priorityGroup === "low"),
        },
        overdue_reviews: queueOptimization.filter((row) => row.queueAgeMinutes >= 240),
        stale_rfqs: queueOptimization.filter((row) => row.staleEvidence),
        overloaded_queue: reviewItems.length >= 1000,
        summary: {
          total: queueOptimization.length,
          urgent: queueOptimization.filter((row) => row.priorityGroup === "urgent").length,
          high: queueOptimization.filter((row) => row.priorityGroup === "high").length,
          medium: queueOptimization.filter((row) => row.priorityGroup === "medium").length,
          low: queueOptimization.filter((row) => row.priorityGroup === "low").length,
          average_priority_score: round(queueOptimization.reduce((sum, row) => sum + row.priorityScore, 0) / queueOptimization.length, 2),
          average_queue_age_minutes: round(queueOptimization.reduce((sum, row) => sum + row.queueAgeMinutes, 0) / queueOptimization.length, 2),
        },
      },
      reviewEfficiency: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        rfqs_reviewed_per_hour: round(reviewItems.length / 2, 2),
        review_completion_time_minutes: 42,
        evidence_handling_time_minutes: 18,
        escalation_frequency: 2,
        reassignment_frequency: 1,
        queue_aging_trends: { average: 42 },
        operator_throughput_trends: { overall: reviewItems.length },
        timeline_gap_minutes: 15,
        throughput_bottlenecks: queueOptimization.slice(0, 5),
        advisory_only: true,
      },
      focusSessions: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        sessions: operators.slice(0, 5).map((row, index) => ({
          operatorId: row.operatorId,
          focusedMinutes: 45 + index * 10,
          reviewThroughput: row.assigned,
          interruptionCount: index,
          completionBursts: Math.max(0, row.assigned - index),
          sessionStart: generatedAt,
          sessionEnd: generatedAt,
        })),
        summary: { sessionCount: 5, totalThroughput: reviewItems.length, totalInterruptions: 10, totalBursts: 12 },
        advisoryOnly: true,
      },
      queueHeatmap: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        heatmap: queueHeatmap,
        operator_distribution: operators.reduce((acc, row) => ({ ...acc, [row.operatorId]: row.assigned }), {}),
        source_distribution: { "Tier 1": 2, "Tier 2": 3, "Tier 3": 4, "Tier 4": 1 },
        escalation_density: { urgent: 1, high: 2, medium: 4, low: 3 },
        province_density: reviewItems.reduce((acc, row) => ({ ...acc, [row.province]: (acc[row.province] || 0) + 1 }), {}),
      },
      reviewPriorities: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        priority_score: 72,
        priority_groups: {
          urgent: queueOptimization.filter((row) => row.priorityGroup === "urgent"),
          high: queueOptimization.filter((row) => row.priorityGroup === "high"),
          medium: queueOptimization.filter((row) => row.priorityGroup === "medium"),
          low: queueOptimization.filter((row) => row.priorityGroup === "low"),
        },
        escalation_recommendations: queueOptimization.slice(0, 5).map((row) => ({
          tenderId: row.tenderId,
          title: row.title,
          recommendation: row.priorityGroup === "urgent" ? "escalate" : "monitor",
          reason: row.priorityReason,
        })),
        review_urgency: reviewItems.length > 10 ? "high" : "normal",
        overloaded_queue: reviewItems.length >= 1000,
      },
      evidenceAcceleration: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        missing_evidence: queueOptimization.filter((row) => row.staleEvidence).slice(0, 5),
        stale_evidence: queueOptimization.filter((row) => row.staleEvidence).slice(0, 8),
        supplier_quote_completeness: queueOptimization.slice(0, 10).map((row) => ({
          tenderId: row.tenderId,
          title: row.title,
          pricingConfidence: row.pricingConfidence,
          queueAgeMinutes: row.queueAgeMinutes,
        })),
        pricing_mismatch_summary: queueOptimization.filter((row) => row.pricingConfidence < 65).slice(0, 8),
        grouped_warnings: { missing_evidence: queueOptimization.filter((row) => row.staleEvidence).length },
        summary: { total: queueOptimization.length, missingEvidence: queueOptimization.filter((row) => row.staleEvidence).length, staleEvidence: queueOptimization.filter((row) => row.staleEvidence).length, pricingMismatches: queueOptimization.filter((row) => row.pricingConfidence < 65).length },
      },
      shortcuts: {
        status: "runtime_fallback",
        generated_at: generatedAt,
        data_source: telemetry.dataSource || "static_seed",
        shortcuts: [
          { label: "Jump to urgent", key: "g u", action: "filter_urgent" },
          { label: "Jump to overdue", key: "g o", action: "filter_overdue" },
          { label: "Mark reviewed", key: "m r", action: "mark_reviewed" },
          { label: "Request clarification", key: "m c", action: "request_clarification" },
        ],
        quickActions: ["assign_operator", "acknowledge_alert", "archive_reviewed"],
        filterPresets: ["urgent", "overdue", "high_value", "stale_evidence"],
        advisoryOnly: true,
      },
    },
    {},
  );
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(Number(value || 0) * factor) / factor;
}

export async function fetchOperatorProductivitySnapshot() {
  const [workload, focusSessions, shortcuts] = await Promise.all([
    axiosAdapter("/productivity/workload"),
    axiosAdapter("/productivity/focus-sessions"),
    axiosAdapter("/productivity/shortcuts"),
  ]);
  const fallback = buildFallbackProductivitySnapshot();
  return normalizeProductivitySnapshot(
    {
      status: "ok",
      generated_at: workload?.generated_at || focusSessions?.generated_at || shortcuts?.generated_at,
      data_source: workload?.data_source || focusSessions?.data_source || shortcuts?.data_source || fallback.dataSource,
      workload,
      focusSessions,
      shortcuts,
      queueOptimization: fallback.queueOptimization,
      reviewEfficiency: fallback.reviewEfficiency,
      queueHeatmap: fallback.queueHeatmap,
      reviewPriorities: fallback.reviewPriorities,
      evidenceAcceleration: fallback.evidenceAcceleration,
    },
    fallback,
  );
}

export async function fetchOperatorWorkloadData() {
  const remote = await axiosAdapter("/productivity/workload");
  const fallback = buildFallbackProductivitySnapshot();
  return normalizeOperatorWorkload(remote || {}, fallback.workload);
}

export async function fetchOperatorFocusSessionsData() {
  const remote = await axiosAdapter("/productivity/focus-sessions");
  const fallback = buildFallbackProductivitySnapshot();
  return normalizeFocusSessions(remote || {}, fallback.focusSessions);
}

export async function fetchOperatorShortcutsData() {
  const remote = await axiosAdapter("/productivity/shortcuts");
  const fallback = buildFallbackProductivitySnapshot();
  return normalizeOperatorShortcuts(remote || {}, fallback.shortcuts);
}

export function buildOperatorProductivityFallbackSnapshot() {
  return buildFallbackProductivitySnapshot();
}

