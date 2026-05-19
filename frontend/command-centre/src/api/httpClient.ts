import axios from "axios";

const baseURL = import.meta.env.VITE_LMCP_API_BASE_URL || "";

export const httpClient = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

export function hasConfiguredApiBaseUrl() {
  return Boolean(baseURL);
}

export async function requestJson(path, config = {}) {
  const response = await httpClient.request({
    url: path,
    method: config.method || "get",
    params: config.params,
    data: config.data,
  });
  return response.data;
}
