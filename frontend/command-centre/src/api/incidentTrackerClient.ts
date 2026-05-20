import { axiosAdapter } from "./axiosAdapter";
import { normalizeIncidentTracker, normalizeRuntimeAlerts } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchIncidentTrackerData() {
  const [incidents, alerts] = await Promise.all([
    axiosAdapter("/operations/incidents"),
    axiosAdapter("/operations/runtime-alerts"),
  ]);
  return {
    incidents: normalizeIncidentTracker(incidents || {}, {
      status: "runtime_fallback",
      generatedAt: new Date().toISOString(),
      dataSource: "static_seed",
      totalIncidents: 0,
      severityCounts: {},
      statusCounts: {},
      activeCriticalIncidents: 0,
      incidents: [],
    }),
    alerts: normalizeRuntimeAlerts(alerts || {}, {
      status: "runtime_fallback",
      generatedAt: useTelemetryStore.getState().lastRefreshedAt,
      dataSource: "static_seed",
      alerts: [],
      total: 0,
      alertSeverities: [],
    }),
  };
}

