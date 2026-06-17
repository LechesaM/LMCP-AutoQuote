import { getJson, postJson } from "./httpClient";

export async function fetchOperatorActions() {
  return getJson("/operator-actions");
}

export async function recordOperatorAction(payload: unknown) {
  return postJson("/operator-actions", payload);
}
