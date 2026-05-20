import { useEffect, useMemo, useState } from "react";
import { fetchBackupValidationData, fetchRuntimeMetricsData } from "../api/runtimeMetricsClient";

export function useRuntimeMetrics({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [backupSnapshot, setBackupSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const [next, nextBackup] = await Promise.all([fetchRuntimeMetricsData(), fetchBackupValidationData()]);
      setSnapshot(next);
      setBackupSnapshot(nextBackup);
      setError("");
      return { next, nextBackup };
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh runtime metrics");
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
      metrics: snapshot?.metrics || {},
      systemHealth: snapshot?.systemHealth || {},
      operatorCapacity: snapshot?.operatorCapacity || {},
      queueSummary: snapshot?.queueSummary || {},
      sourceSummary: snapshot?.sourceSummary || {},
      workflowSummary: snapshot?.workflowSummary || {},
      persistence: snapshot?.persistence || {},
      backupValidation: backupSnapshot || {},
      refresh,
    }),
    [snapshot, backupSnapshot, loading, refreshing, error],
  );
}
