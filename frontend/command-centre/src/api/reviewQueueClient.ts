import { getJson } from "./httpClient";

export async function fetchReviewQueue() {
  return getJson("/telemetry/review-queue");
}
