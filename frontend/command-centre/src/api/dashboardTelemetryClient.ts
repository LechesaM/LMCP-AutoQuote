import { axiosAdapter } from "./axiosAdapter";
import { normalizeDashboardTelemetry } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchDashboardTelemetry() {
  const remote = await axiosAdapter("/api/dashboard/telemetry");
  if (remote) {
    return normalizeDashboardTelemetry(remote);
  }
  return normalizeDashboardTelemetry(useTelemetryStore.getState().commandMetrics);
}
