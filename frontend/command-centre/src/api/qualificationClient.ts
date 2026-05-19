import { axiosAdapter } from "./axiosAdapter";
import { normalizeQualificationSummary } from "./normalize";

export async function fetchQualificationSummaryData() {
  const remote = await axiosAdapter("/telemetry/qualification");
  if (remote) {
    return normalizeQualificationSummary(remote);
  }
  return normalizeQualificationSummary({
    status: "runtime_fallback",
    manualGovernanceOnly: true,
    reviewReadyRequired: true,
    proofCaptureRequired: true,
  });
}
