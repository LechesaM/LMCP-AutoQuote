import { axiosAdapter } from "./axiosAdapter";
import { normalizeHarvestHealth } from "./normalize";
import useSourceHealthStore from "../store/sourceHealthStore";

export async function fetchSourceHealthData() {
  const remote = await axiosAdapter("/api/harvest/source-health");
  if (remote) {
    return normalizeHarvestHealth(remote);
  }
  return normalizeHarvestHealth({
    status: "advisory",
    sources: useSourceHealthStore.getState().sources,
  });
}
