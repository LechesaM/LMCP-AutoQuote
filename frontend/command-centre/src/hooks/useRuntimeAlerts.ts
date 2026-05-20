import { useEffect, useMemo, useState } from "react";
import { axiosAdapter } from "../api/axiosAdapter";
import { normalizeRuntimeAlerts } from "../api/normalize";
import useTelemetryStore from "../store/telemetryStore";

async function fetchRuntimeAlertsData() {
  const remote = await axiosAdapter("/operations/runtime-alerts");
  return normalizeRuntimeAlerts(remote || {}, {
    status: "runtime_fallback",
    generatedAt: useTelemetryStore.getState().lastRefreshedAt,
    dataSource: "static_seed",
    alerts: useTelemetryStore.getState().recentAlerts.map((message, index) => ({
      alertId: `alert-${index}`,
      type: "info",
      severity: "info",
      title: "Telemetry alert",
      message,
      createdAt: useTelemetryStore.getState().lastRefreshedAt,
      acknowledged: false,
      details: {},
    })),
    total: useTelemetryStore.getState().recentAlerts.length,
    alertSeverities: ["info"],
  });
}

export function useRuntimeAlerts({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchRuntimeAlertsData();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh alerts");
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
      alerts: snapshot?.alerts || [],
      total: snapshot?.total || 0,
      alertSeverities: snapshot?.alertSeverities || [],
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}
