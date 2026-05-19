import { fetchReviewQueueData } from "./reviewQueueClient";

export async function fetchReviewQueue() {
  const snapshot = await fetchReviewQueueData();
  return snapshot.items;
}

export async function fetchReviewSummary() {
  const snapshot = await fetchReviewQueueData();
  return snapshot.summary;
}
