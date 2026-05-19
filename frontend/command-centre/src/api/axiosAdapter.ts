import { hasConfiguredApiBaseUrl, requestJson } from "./httpClient";

export async function axiosAdapter(path, config = {}) {
  if (!hasConfiguredApiBaseUrl()) {
    return null;
  }
  return requestJson(path, config);
}
