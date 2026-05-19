import { axiosAdapter } from "./axiosAdapter";
import { normalizeReviewQueue } from "./normalize";
import useQueueStore from "../store/queueStore";

export async function fetchReviewQueueData() {
  const remote = await axiosAdapter("/api/review/queue");
  if (remote) {
    return normalizeReviewQueue(remote);
  }
  return normalizeReviewQueue(useQueueStore.getState());
}
