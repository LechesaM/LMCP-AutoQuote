import { getJson, postJson } from "../api/httpClient";

export async function login(payload: { email: string; password: string }) {
  return postJson("/auth/login", payload);
}

export async function getCurrentUser() {
  return getJson("/auth/me");
}
