import { axiosAdapter } from "./axiosAdapter";
import {
  normalizeEvidenceAcceleration,
  normalizeFocusSessions,
  normalizeReviewEfficiency,
} from "./normalize";
import { buildOperatorProductivityFallbackSnapshot } from "./operatorProductivityClient";

export async function fetchReviewEfficiencyData() {
  const remote = await axiosAdapter("/productivity/review-efficiency");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeReviewEfficiency(remote || {}, fallback.reviewEfficiency);
}

export async function fetchEvidenceAccelerationData() {
  const remote = await axiosAdapter("/productivity/evidence-acceleration");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeEvidenceAcceleration(remote || {}, fallback.evidenceAcceleration);
}

export async function fetchFocusSessionsData() {
  const remote = await axiosAdapter("/productivity/focus-sessions");
  const fallback = buildOperatorProductivityFallbackSnapshot();
  return normalizeFocusSessions(remote || {}, fallback.focusSessions);
}

