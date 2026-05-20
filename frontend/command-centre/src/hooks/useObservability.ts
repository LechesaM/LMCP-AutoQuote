import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchObservabilitySnapshot } from "../api/observabilityClient";

export function useObservability({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const snapshotRef = useRef(snapshot);
  const loadingRef = useRef(loading);
  const refreshingRef = useRef(refreshing);
  const errorRef = useRef(error);

  const commitSnapshot = useCallback((next) => {
    setSnapshot((current) => {
      if (JSON.stringify(current ?? {}) === JSON.stringify(next ?? {})) {
        return current;
      }
      snapshotRef.current = next;
      return next;
    });
  }, []);

  const commitLoading = useCallback((nextValue) => {
    setLoading((current) => {
      if (current === nextValue) {
        return current;
      }
      loadingRef.current = nextValue;
      return nextValue;
    });
  }, []);

  const commitRefreshing = useCallback((nextValue) => {
    setRefreshing((current) => {
      if (current === nextValue) {
        return current;
      }
      refreshingRef.current = nextValue;
      return nextValue;
    });
  }, []);

  const commitError = useCallback((message) => {
    setError((current) => {
      if (current === message) {
        return current;
      }
      errorRef.current = message;
      return message;
    });
  }, []);

  const refresh = useCallback(async () => {
    commitRefreshing(true);
    try {
      const next = await fetchObservabilitySnapshot();
      commitSnapshot(next);
      commitError("");
      return next;
    } catch (exception) {
      commitError(exception instanceof Error ? exception.message : "Unable to refresh observability snapshot");
      return null;
    } finally {
      commitLoading(false);
      commitRefreshing(false);
    }
  }, [commitError, commitLoading, commitRefreshing, commitSnapshot]);

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
  }, [intervalMs, refresh]);

  return useMemo(
    () => ({
      loading: loadingRef.current,
      refreshing: refreshingRef.current,
      error: errorRef.current,
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
    [snapshot, loading, refreshing, error, refresh],
  );
}
