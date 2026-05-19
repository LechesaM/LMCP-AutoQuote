import { axiosAdapter } from "./axiosAdapter";
import { normalizeHarvestHealth } from "./normalize";
import useSourceHealthStore from "../store/sourceHealthStore";

export async function fetchSourceHealthData() {
  const remote = await axiosAdapter("/telemetry/source-health");
  if (remote) {
    return normalizeHarvestHealth(remote, useSourceHealthStore.getState());
  }
  return normalizeHarvestHealth({
    status: "runtime_fallback",
    sources: useSourceHealthStore.getState().sources,
  }, useSourceHealthStore.getState());
}
