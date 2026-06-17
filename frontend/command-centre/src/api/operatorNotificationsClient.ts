import { getJson } from "./httpClient";

export async function fetchOperatorNotifications() {
  return getJson("/operator-notifications");
}
