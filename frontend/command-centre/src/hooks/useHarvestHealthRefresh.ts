import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchSourceHealthData } from "../api/sourceHealthClient";
import useSourceHealthStore from "../store/sourceHealthStore";

export function useHarvestHealthRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    useSourceHealthStore.setState({ loading: true, refreshing: true, error: "" });
    const hub = createRefreshHub(async () => {
      const nextHealth = await fetchSourceHealthData();
      useSourceHealthStore.getState().setSourceHealthSnapshot(nextHealth);
      return nextHealth;
    }, {
      intervalMs,
      enableWebSocket,
      websocketUrl,
    });

    hub.start();
    hub.refresh().catch((error) => {
      useSourceHealthStore.setState({
        loading: false,
        refreshing: false,
        stale: true,
        error: error instanceof Error ? error.message : "Unable to refresh source health",
      });
    });
    return () => hub.stop();
  }, [intervalMs, enableWebSocket, websocketUrl]);
}
