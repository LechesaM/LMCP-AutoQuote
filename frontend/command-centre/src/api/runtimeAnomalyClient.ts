import { axiosAdapter } from "./axiosAdapter";
import { normalizeRuntimeAnomalies } from "./normalize";
import { fetchRuntimeAnomalyData as fetchFallbackRuntimeAnomalyData } from "./observabilityClient";

export async function fetchRuntimeAnomalyData() {
  const remote = await axiosAdapter("/observability/anomalies");
  if (remote) {
    return normalizeRuntimeAnomalies(remote, {});
  }
  return fetchFallbackRuntimeAnomalyData();
}
