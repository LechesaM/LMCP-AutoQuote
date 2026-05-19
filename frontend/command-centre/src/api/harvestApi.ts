import { fetchSourceHealthData } from "./sourceHealthClient";

export async function fetchHarvestSources() {
  const snapshot = await fetchSourceHealthData();
  return snapshot.sources;
}

export async function fetchHarvestHealth() {
  return fetchSourceHealthData();
}
