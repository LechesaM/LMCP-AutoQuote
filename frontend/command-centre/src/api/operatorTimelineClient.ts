import { axiosAdapter } from "./axiosAdapter";
import { normalizeOperatorTimeline } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";
import useQueueStore from "../store/queueStore";

function buildFallbackTimeline() {
  const telemetry = useTelemetryStore.getState();
  const queue = useQueueStore.getState();
  const now = new Date().toISOString();
  const events = [
    ...(queue.summary?.alerts || []).slice(0, 4).map((alert, index) => ({
      eventId: `fallback-event-${index + 1}`,
      eventType: "queue_alert",
      operatorId: `operator-${(index % 10) + 1}`,
      tenderId: "",
      title: String(alert),
      severity: index === 0 ? "critical" : "warning",
      reversible: true,
      reviewable: true,
      createdAt: now,
      details: { source: "queue_summary" },
    })),
    ...(telemetry.recentAlerts || []).slice(0, 4).map((alert, index) => ({
      eventId: `fallback-telemetry-${index + 1}`,
      eventType: "telemetry_alert",
      operatorId: "",
      tenderId: "",
      title: String(alert),
      severity: "warning",
      reversible: true,
      reviewable: true,
      createdAt: now,
      details: { source: "telemetry" },
    })),
  ];
  return normalizeOperatorTimeline({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || now,
    dataSource: telemetry.dataSource || "static_seed",
    events,
    total: events.length,
  });
}

export async function fetchOperatorTimeline(limit = 100) {
  const remote = await axiosAdapter("/operator/timeline", { params: { limit } });
  if (remote?.events) {
    return normalizeOperatorTimeline(remote);
  }
  return buildFallbackTimeline();
}
