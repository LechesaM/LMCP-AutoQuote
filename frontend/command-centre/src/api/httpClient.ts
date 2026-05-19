import axios from "axios";
import { AUTH_STORAGE_KEY } from "../auth/authConstants";

const baseURL = import.meta.env.VITE_LMCP_API_BASE_URL || "";

export const httpClient = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

httpClient.interceptors.request.use((config) => {
  try {
    const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_STORAGE_KEY) : "";
    const authToken = token ? JSON.parse(token)?.state?.token : "";
    if (authToken) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${authToken}`;
    }
  } catch (error) {
    // ignore auth header hydration issues
  }
  return config;
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
