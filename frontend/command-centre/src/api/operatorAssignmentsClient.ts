import { getJson } from "./httpClient";

export async function fetchOperatorAssignments() {
  return getJson("/operations/assignments");
}
