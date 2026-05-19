import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchDashboardTelemetry } from "../api/dashboardTelemetryClient";
import useTelemetryStore from "../store/telemetryStore";

export function useTelemetryRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    useTelemetryStore.getState().setTelemetryStatus({ loading: true, refreshing: true, error: "" });
    const hub = createRefreshHub(async () => {
      const nextTelemetry = await fetchDashboardTelemetry();
      useTelemetryStore.getState().setTelemetrySnapshot(nextTelemetry);
      return nextTelemetry;
    }, {
      intervalMs,
      enableWebSocket,
      websocketUrl,
    });

    hub.start();
    hub.refresh().catch((error) => {
      useTelemetryStore.getState().setTelemetryStatus({
        loading: false,
        refreshing: false,
        stale: true,
        error: error instanceof Error ? error.message : "Unable to refresh telemetry",
      });
    });
    return () => hub.stop();
  }, [intervalMs, enableWebSocket, websocketUrl]);
}
