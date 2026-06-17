import { getJson } from "./httpClient";

export async function fetchSourceHealth() {
  return getJson("/telemetry/source-health");
}
