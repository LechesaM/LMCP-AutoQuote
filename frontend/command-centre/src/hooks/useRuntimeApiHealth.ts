import { useEffect, useMemo, useState } from "react";
import { requestJson, hasConfiguredApiBaseUrl } from "../api/httpClient";

const initialHealth = {
  status: hasConfiguredApiBaseUrl() ? "loading" : "degraded",
  dataSource: hasConfiguredApiBaseUrl() ? "runtime" : "runtime_fallback",
  error: hasConfiguredApiBaseUrl() ? "" : "API base URL is not configured",
  latencyMs: 0,
  lastCheckedAt: "",
  route: "/observability/uptime",
  response: null,
};

export function useRuntimeApiHealth({ intervalMs = 45000 } = {}) {
  const [state, setState] = useState(initialHealth);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      if (!hasConfiguredApiBaseUrl()) {
        if (active) {
          setState((current) => ({
            ...current,
            status: "degraded",
            dataSource: "runtime_fallback",
            error: "API base URL is not configured",
            lastCheckedAt: new Date().toISOString(),
          }));
        }
        return;
      }
      const startedAt = Date.now();
      try {
        const response = await requestJson("/observability/uptime");
        if (!active) {
          return;
        }
        setState({
          status: response?.status === "healthy" ? "healthy" : "degraded",
          dataSource: response?.data_source || "runtime",
          error: response?.status === "healthy" ? "" : response?.message || "API reported a degraded status",
          latencyMs: Date.now() - startedAt,
          lastCheckedAt: new Date().toISOString(),
          route: "/observability/uptime",
          response,
        });
      } catch (error) {
        if (!active) {
          return;
        }
        setState({
          status: "degraded",
          dataSource: "runtime_fallback",
          error: error instanceof Error ? error.message : "Unable to reach API health endpoint",
          latencyMs: Date.now() - startedAt,
          lastCheckedAt: new Date().toISOString(),
          route: "/observability/uptime",
          response: null,
        });
      }
    };

    refresh();
    const timer = window.setInterval(refresh, Math.max(15000, Number(intervalMs) || 45000));

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return useMemo(
    () => ({
      ...state,
      healthy: state.status === "healthy",
      degraded: state.status !== "healthy",
      refresh: async () => {
        if (!hasConfiguredApiBaseUrl()) {
          setState((current) => ({
            ...current,
            status: "degraded",
            dataSource: "runtime_fallback",
            error: "API base URL is not configured",
            lastCheckedAt: new Date().toISOString(),
          }));
          return null;
        }
        const startedAt = Date.now();
        try {
          const response = await requestJson("/observability/uptime");
          setState({
            status: response?.status === "healthy" ? "healthy" : "degraded",
            dataSource: response?.data_source || "runtime",
            error: response?.status === "healthy" ? "" : response?.message || "API reported a degraded status",
            latencyMs: Date.now() - startedAt,
            lastCheckedAt: new Date().toISOString(),
            route: "/observability/uptime",
            response,
          });
          return response;
        } catch (error) {
          setState({
            status: "degraded",
            dataSource: "runtime_fallback",
            error: error instanceof Error ? error.message : "Unable to reach API health endpoint",
            latencyMs: Date.now() - startedAt,
            lastCheckedAt: new Date().toISOString(),
            route: "/observability/uptime",
            response: null,
          });
          return null;
        }
      },
    }),
    [state],
  );
}
