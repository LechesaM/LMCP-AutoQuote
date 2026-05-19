import { hasConfiguredApiBaseUrl, requestJson } from "./httpClient";

export async function axiosAdapter(path, config = {}) {
  if (!hasConfiguredApiBaseUrl()) {
    return null;
  }
  try {
    return await requestJson(path, config);
  } catch (error) {
    return null;
  }
}
