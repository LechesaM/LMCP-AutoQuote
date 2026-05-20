import { useEffect, useMemo, useState } from "react";
import { fetchObservabilitySnapshot } from "../api/observabilityClient";

export function useObservability({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchObservabilitySnapshot();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh observability snapshot");
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    let active = true;
    const tick = async () => {
      if (!active) return;
      await refresh();
    };
    tick();
    const timer = window.setInterval(() => {
      tick().catch(() => {});
    }, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return useMemo(
    () => ({
      loading,
      refreshing,
      error,
      stale: Boolean(error) || (snapshot?.dataSource || "runtime_fallback") !== "runtime",
      dataSource: snapshot?.dataSource || "runtime_fallback",
      lastUpdated: snapshot?.generatedAt || "",
      prometheus: snapshot?.prometheus || {},
      grafana: snapshot?.grafana || {},
      sentry: snapshot?.sentry || {},
      sla: snapshot?.sla || {},
      anomalies: snapshot?.anomalies || {},
      alerts: snapshot?.alerts || {},
      logs: snapshot?.logs || {},
      uptime: snapshot?.uptime || {},
      performance: snapshot?.performance || {},
      summary: snapshot?.summary || {},
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
