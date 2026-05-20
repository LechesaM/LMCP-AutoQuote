import { useEffect, useMemo, useState } from "react";
import { fetchIncidentTrackerData } from "../api/incidentTrackerClient";

export function useIncidentTracker({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchIncidentTrackerData();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh incidents");
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
      stale: Boolean(error) || (snapshot?.incidents?.dataSource || snapshot?.alerts?.dataSource || "runtime_fallback") !== "runtime",
      dataSource: snapshot?.incidents?.dataSource || snapshot?.alerts?.dataSource || "runtime_fallback",
      lastUpdated: snapshot?.incidents?.generatedAt || snapshot?.alerts?.generatedAt || "",
      incidents: snapshot?.incidents?.incidents || [],
      incidentSummary: snapshot?.incidents || {},
      alerts: snapshot?.alerts?.alerts || [],
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
