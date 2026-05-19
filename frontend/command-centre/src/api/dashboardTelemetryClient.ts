import { axiosAdapter } from "./axiosAdapter";
import { normalizeDashboardTelemetry } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

export async function fetchDashboardTelemetry() {
  const remote = await axiosAdapter("/telemetry/dashboard");
  if (remote) {
    return normalizeDashboardTelemetry(remote, useTelemetryStore.getState());
  }
  return normalizeDashboardTelemetry(useTelemetryStore.getState(), useTelemetryStore.getState());
}
