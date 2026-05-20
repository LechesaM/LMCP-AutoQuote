import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeQueueHeatmap,
  normalizeReviewPriorities,
  normalizeReviewQueueOptimization,
} from "./normalize";
import { buildOperatorProductivityFallbackSnapshot } from "./operatorProductivityClient";

export async function fetchReviewQueueOptimizationData() {
  const remote = await axiosAdapter("/productivity/queue-optimization");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeReviewQueueOptimization(remote || {}, fallback.queueOptimization);
}

export async function fetchQueueHeatmapData() {
  const remote = await axiosAdapter("/productivity/queue-heatmap");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeQueueHeatmap(remote || {}, fallback.queueHeatmap);
}

export async function fetchReviewPrioritiesData() {
  const remote = await axiosAdapter("/productivity/review-priorities");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeReviewPriorities(remote || {}, fallback.reviewPriorities);
}

