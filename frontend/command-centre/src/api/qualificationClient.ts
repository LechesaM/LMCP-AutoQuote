import { getJson } from "./httpClient";

export async function fetchQualificationSummary() {
  return getJson("/telemetry/qualification");
}
