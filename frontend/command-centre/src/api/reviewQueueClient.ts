import { axiosAdapter } from "./axiosAdapter";
import { normalizeReviewQueue } from "./normalize";
import useQueueStore from "../store/queueStore";

export async function fetchReviewQueueData() {
  const remote = await axiosAdapter("/telemetry/review-queue");
  if (remote) {
    return normalizeReviewQueue(remote, useQueueStore.getState());
  }
  return normalizeReviewQueue({
    status: "runtime_fallback",
    items: useQueueStore.getState().items,
    summary: useQueueStore.getState().summary,
  }, useQueueStore.getState());
}
