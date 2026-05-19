import { axiosAdapter } from "./axiosAdapter";
import { normalizeOperatorAssignments, normalizeOperatorCapacity } from "./normalize";
import useQueueStore from "../store/queueStore";
import useTelemetryStore from "../store/telemetryStore";

function buildFallbackAssignments() {
  const queue = useQueueStore.getState();
  const telemetry = useTelemetryStore.getState();
  const items = queue.items || [];
  const now = new Date().toISOString();
  return normalizeOperatorAssignments({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || now,
    dataSource: telemetry.dataSource || "static_seed",
    assignments: items.slice(0, 10).map((item, index) => ({
      assignmentId: `fallback-assignment-${index + 1}`,
      operatorId: `operator-${(index % 10) + 1}`,
      tenderId: item.id,
      status: index < 3 ? "overdue" : "assigned",
      priority: index === 0 ? 100 : 75 - index,
      assignedAt: now,
      dueAt: now,
      workload: items.length,
      recommendation: item.recommendation || "manual",
      source: "static_seed",
      details: { title: item.title, province: item.province, profit: item.profit, value: item.value },
    })),
    recommendations: items.slice(0, 10).map((item, index) => ({
      tenderId: item.id,
      title: item.title,
      recommendation: item.recommendation || "manual",
      priority: index === 0 ? 100 : 75 - index,
      workflowStage: item.recommendation === "GO" ? "approved" : "review_ready",
      owner: `operator-${(index % 10) + 1}`,
      reason: item.recommendation === "GO" ? "GO candidate prioritized" : "Manual review recommended",
      dueAt: now,
    })),
    summary: {
      totalAssignments: items.length,
      activeAssignments: items.length,
      operators: 10,
      capacity: 1000,
    },
    capacity: {
      status: "ok",
      generatedAt: telemetry.lastRefreshedAt || now,
      dataSource: telemetry.dataSource || "static_seed",
      teamSize: 10,
      perOperatorDailyCapacity: 100,
      totalDailyCapacity: 1000,
      assignedToday: items.length,
      remainingCapacity: Math.max(0, 1000 - items.length),
      overloaded: items.length >= 1000,
      recommendedLoad: items.length,
    },
  });
}

export async function fetchOperatorAssignments(limit = 100) {
  const remote = await axiosAdapter("/operator/assignments", { params: { limit } });
  if (remote?.assignments) {
    return normalizeOperatorAssignments(remote);
  }
  return buildFallbackAssignments();
}

export async function fetchOperatorCapacity() {
  const remote = await axiosAdapter("/operator/capacity");
  if (remote?.totalDailyCapacity) {
    return normalizeOperatorCapacity(remote);
  }
  const fallback = buildFallbackAssignments();
  return fallback.capacity;
}
