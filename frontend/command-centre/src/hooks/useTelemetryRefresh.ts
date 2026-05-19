import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchDashboardTelemetry } from "../api/dashboardTelemetryClient";
import useTelemetryStore from "../store/telemetryStore";

export function useTelemetryRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    const hub = createRefreshHub(async () => {
      const nextTelemetry = await fetchDashboardTelemetry();
      useTelemetryStore.setState({
        commandMetrics: nextTelemetry,
      });
      return nextTelemetry;
    }, {
      intervalMs,
      enableWebSocket,
      websocketUrl,
    });

    hub.start();
    hub.refresh().catch(() => {});
    return () => hub.stop();
  }, [intervalMs, enableWebSocket, websocketUrl]);
}
