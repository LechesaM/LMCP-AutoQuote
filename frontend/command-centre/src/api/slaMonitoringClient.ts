import { axiosAdapter } from "./axiosAdapter";
import { normalizeSlaMonitoring } from "./normalize";
import { fetchSlaMonitoringData as fetchFallbackSlaMonitoringData } from "./observabilityClient";

export async function fetchSlaMonitoringData() {
  const remote = await axiosAdapter("/observability/sla");
  if (remote) {
    return normalizeSlaMonitoring(remote, {});
  }
  return fetchFallbackSlaMonitoringData();
}
