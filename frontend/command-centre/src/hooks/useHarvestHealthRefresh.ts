import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchSourceHealthData } from "../api/sourceHealthClient";
import useSourceHealthStore from "../store/sourceHealthStore";

export function useHarvestHealthRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    const hub = createRefreshHub(async () => {
      const nextHealth = await fetchSourceHealthData();
      useSourceHealthStore.setState({ sources: nextHealth.sources });
      return nextHealth;
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
