import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { requestJson, hasConfiguredApiBaseUrl } from "../api/httpClient";
import { sameRuntimeApiHealth } from "../store/telemetryGuards.js";

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
  const stateRef = useRef(state);
  const activeRef = useRef(true);

  const commitState = useCallback((nextState) => {
    setState((current) => {
      if (sameRuntimeApiHealth(current, nextState)) {
        return current;
      }
      stateRef.current = nextState;
      return nextState;
    });
  }, []);

  const refresh = useCallback(async () => {
    if (!activeRef.current) {
      return null;
    }
    if (!hasConfiguredApiBaseUrl()) {
      commitState({
        ...stateRef.current,
        status: "degraded",
        dataSource: "runtime_fallback",
        error: "API base URL is not configured",
        lastCheckedAt: new Date().toISOString(),
        route: "/observability/uptime",
        response: null,
      });
      return null;
    }

    const startedAt = Date.now();
    try {
      const response = await requestJson("/observability/uptime");
      const nextState = {
        status: response?.status === "healthy" ? "healthy" : "degraded",
        dataSource: response?.data_source || "runtime",
        error: response?.status === "healthy" ? "" : response?.message || "API reported a degraded status",
        latencyMs: Date.now() - startedAt,
        lastCheckedAt: new Date().toISOString(),
        route: "/observability/uptime",
        response,
      };
      commitState(nextState);
      return response;
    } catch (error) {
      const nextState = {
        status: "degraded",
        dataSource: "runtime_fallback",
        error: error instanceof Error ? error.message : "Unable to reach API health endpoint",
        latencyMs: Date.now() - startedAt,
        lastCheckedAt: new Date().toISOString(),
        route: "/observability/uptime",
        response: null,
      };
      commitState(nextState);
      return null;
    }
  }, [commitState]);

  useEffect(() => {
    activeRef.current = true;
    refresh().catch(() => {});
    const timer = window.setInterval(refresh, Math.max(15000, Number(intervalMs) || 45000));

    return () => {
      activeRef.current = false;
      window.clearInterval(timer);
    };
  }, [intervalMs, refresh]);

  return useMemo(
    () => ({
      ...state,
      healthy: state.status === "healthy",
      degraded: state.status !== "healthy",
      refresh,
    }),
    [state, refresh],
  );
}
