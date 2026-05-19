import { requestJson } from "../api/httpClient";

export async function loginWithCredentials(email, password) {
  return requestJson("/auth/login", { method: "post", data: { email, password } });
}

export async function logoutSession() {
  return requestJson("/auth/logout", { method: "post" });
}

export async function fetchCurrentUser() {
  return requestJson("/auth/me");
}

export async function fetchCurrentPermissions() {
  return requestJson("/auth/permissions");
}

