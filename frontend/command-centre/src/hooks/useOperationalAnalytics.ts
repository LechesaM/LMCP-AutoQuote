import { useEffect, useMemo, useState } from "react";
import { fetchOperationalAnalyticsData } from "../api/operationalAnalyticsClient";

export function useOperationalAnalytics({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchOperationalAnalyticsData();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh operational analytics");
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    let active = true;
    const tick = async () => {
      if (!active) {
        return;
      }
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
      operatorAnalytics: snapshot?.operatorAnalytics || {},
      sourceReliability: snapshot?.sourceReliability || {},
      runtimeMetrics: snapshot?.runtimeMetrics || {},
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
