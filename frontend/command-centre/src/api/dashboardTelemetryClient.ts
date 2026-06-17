import { getJson } from "./httpClient";

export async function fetchDashboardTelemetry() {
  return getJson("/telemetry/dashboard");
}
