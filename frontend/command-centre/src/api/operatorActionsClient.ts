import { axiosAdapter } from "./axiosAdapter";
import { requestJson } from "./httpClient";
import { normalizeOperatorActions } from "./normalize";
import useQueueStore from "../store/queueStore";
import useTelemetryStore from "../store/telemetryStore";

function buildFallbackActions() {
  const queueItems = useQueueStore.getState().items || [];
  const telemetry = useTelemetryStore.getState();
  return normalizeOperatorActions({
    status: "ok",
    generatedAt: telemetry.lastRefreshedAt || new Date().toISOString(),
    dataSource: telemetry.dataSource || "static_seed",
    actions: queueItems.slice(0, 8).map((item, index) => ({
      actionId: `fallback-action-${index + 1}`,
      action: index === 0 ? "assign_operator" : "mark_reviewed",
      operatorId: `operator-${(index % 10) + 1}`,
      tenderId: item.id,
      targetType: "rfq",
      note: item.title,
      status: "queued_for_manual_followup",
      reversible: true,
      reviewable: true,
      createdAt: telemetry.lastRefreshedAt || new Date().toISOString(),
      updatedAt: telemetry.lastRefreshedAt || new Date().toISOString(),
      details: { recommendation: item.recommendation, value: item.value, profit: item.profit },
    })),
    total: queueItems.length,
  });
}

export async function fetchOperatorActions(limit = 100) {
  const remote = await axiosAdapter("/operator/actions", { params: { limit } });
  if (remote?.actions) {
    return normalizeOperatorActions(remote);
  }
  return buildFallbackActions();
}

export async function postOperatorAction(actionPath, payload) {
  return requestJson(actionPath, { method: "post", data: payload });
}
