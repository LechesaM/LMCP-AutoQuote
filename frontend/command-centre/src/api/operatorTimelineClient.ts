import { getJson } from "./httpClient";

export async function fetchOperatorTimeline() {
  return getJson("/operations/timeline");
}
