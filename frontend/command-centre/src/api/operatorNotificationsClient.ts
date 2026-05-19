import { axiosAdapter } from "./axiosAdapter";
import { normalizeOperatorNotifications } from "./normalize";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

function buildFallbackNotifications() {
  const queue = useQueueStore.getState();
  const sources = useSourceHealthStore.getState();
  const telemetry = useTelemetryStore.getState();
  const now = new Date().toISOString();
  const notifications = [];

  if ((queue.summary?.queueLagMinutes || 0) > 0) {
    notifications.push({
      notificationId: "fallback-queue-lag",
      type: "queue_lag",
      severity: "warning",
      title: "Queue lag detected",
      message: `Queue lag is ${queue.summary.queueLagMinutes} minutes.`,
      tenderId: "",
      operatorId: "",
      acknowledged: false,
      createdAt: now,
      details: { queueLagMinutes: queue.summary.queueLagMinutes },
    });
  }

  if ((sources.summary?.failingSources || 0) > 0) {
    notifications.push({
      notificationId: "fallback-source-failure",
      type: "source_failure",
      severity: "critical",
      title: "Source failures detected",
      message: `${sources.summary.failingSources} sources are failing or degraded.`,
      tenderId: "",
      operatorId: "",
      acknowledged: false,
      createdAt: now,
      details: { failingSources: sources.summary.failingSources },
    });
  }

  if ((telemetry.recentAlerts || []).length) {
    notifications.push({
      notificationId: "fallback-governance-warning",
      type: "governance_warning",
      severity: "info",
      title: "Governance telemetry present",
      message: String(telemetry.recentAlerts[0]),
      tenderId: "",
      operatorId: "",
      acknowledged: false,
      createdAt: now,
      details: { recentAlert: telemetry.recentAlerts[0] },
    });
  }

  if (!notifications.length) {
    notifications.push({
      notificationId: "fallback-info",
      type: "info",
      severity: "info",
      title: "No active notifications",
      message: "Operator workspace is stable.",
      tenderId: "",
      operatorId: "",
      acknowledged: false,
      createdAt: now,
      details: {},
    });
  }

  return normalizeOperatorNotifications({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || now,
    dataSource: telemetry.dataSource || "static_seed",
    notifications,
  });
}

export async function fetchOperatorNotifications(limit = 100) {
  const remote = await axiosAdapter("/operator/notifications", { params: { limit } });
  if (remote?.notifications) {
    return normalizeOperatorNotifications(remote);
  }
  return buildFallbackNotifications();
}
