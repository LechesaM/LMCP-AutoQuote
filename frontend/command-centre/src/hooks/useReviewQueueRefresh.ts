import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchReviewQueueData } from "../api/reviewQueueClient";
import useQueueStore from "../store/queueStore";

export function useReviewQueueRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    useQueueStore.setState({ loading: true, refreshing: true, error: "" });
    const hub = createRefreshHub(async () => {
      const nextQueue = await fetchReviewQueueData();
      useQueueStore.getState().setQueueSnapshot(nextQueue);
      return nextQueue;
    }, {
      intervalMs,
      enableWebSocket,
      websocketUrl,
    });

    hub.start();
    hub.refresh().catch((error) => {
      useQueueStore.setState({
        loading: false,
        refreshing: false,
        stale: true,
        error: error instanceof Error ? error.message : "Unable to refresh review queue",
      });
    });
    return () => hub.stop();
  }, [intervalMs, enableWebSocket, websocketUrl]);
}
