import { useEffect, useMemo, useState } from "react";
import { fetchRuntimeStabilityData } from "../api/runtimeStabilityClient";

export function useRuntimeStability({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchRuntimeStabilityData();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh runtime stability");
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
      stale: Boolean(error) || (snapshot?.runtimeStability?.dataSource || snapshot?.dataSource || "runtime_fallback") !== "runtime",
      dataSource: snapshot?.dataSource || snapshot?.runtimeStability?.dataSource || "runtime_fallback",
      lastUpdated: snapshot?.generatedAt || snapshot?.runtimeStability?.generatedAt || "",
      runtimeStability: snapshot?.runtimeStability || {},
      fallbackHealth: snapshot?.fallbackHealth || {},
      telemetryNoise: snapshot?.telemetryNoise || {},
      governanceConsistency: snapshot?.governanceConsistency || {},
      deploymentStability: snapshot?.deploymentStability || {},
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
