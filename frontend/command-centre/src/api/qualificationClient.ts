import { axiosAdapter } from "./axiosAdapter";
import { normalizeQualificationSummary } from "./normalize";

export async function fetchQualificationSummaryData() {
  const remote = await axiosAdapter("/api/qualification/summary");
  if (remote) {
    return normalizeQualificationSummary(remote);
  }
  return normalizeQualificationSummary({
    manualGovernanceOnly: true,
    reviewReadyRequired: true,
    proofCaptureRequired: true,
  });
}
