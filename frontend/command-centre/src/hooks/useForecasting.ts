import { useEffect, useMemo, useState } from "react";
import { fetchForecastingAnalytics } from "../api/forecastingClient";

export function useForecasting({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchForecastingAnalytics();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh forecasting analytics");
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
      summary: snapshot?.summary || {},
      forecast: snapshot?.forecast || {},
      advisoryOnly: snapshot?.advisoryOnly ?? true,
      estimated: snapshot?.estimated ?? true,
      heuristic: snapshot?.heuristic ?? true,
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}

