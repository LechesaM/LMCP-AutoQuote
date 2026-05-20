import { useEffect, useMemo, useState } from "react";
import { fetchOperatorFeedbackData } from "../api/operatorFeedbackClient";

export function useOperatorFeedback({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchOperatorFeedbackData();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh operator feedback");
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
      stale: Boolean(error) || (snapshot?.fatigue?.dataSource || snapshot?.feedback?.dataSource || snapshot?.cleanup?.dataSource || "runtime_fallback") !== "runtime",
      dataSource: snapshot?.fatigue?.dataSource || snapshot?.feedback?.dataSource || snapshot?.cleanup?.dataSource || "runtime_fallback",
      lastUpdated: snapshot?.generatedAt || snapshot?.fatigue?.generatedAt || snapshot?.feedback?.generatedAt || snapshot?.cleanup?.generatedAt || "",
      fatigue: snapshot?.fatigue || {},
      feedback: snapshot?.feedback || {},
      cleanup: snapshot?.cleanup || {},
      fallbackHealth: snapshot?.fallbackHealth || {},
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
