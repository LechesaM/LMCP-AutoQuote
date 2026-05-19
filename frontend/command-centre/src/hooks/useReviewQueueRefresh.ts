import { useEffect } from "react";
import { createRefreshHub } from "../services/refresh/refreshHub";
import { fetchReviewQueueData } from "../api/reviewQueueClient";
import useQueueStore from "../store/queueStore";

export function useReviewQueueRefresh({ intervalMs = 30000, enableWebSocket = false, websocketUrl = "" } = {}) {
  useEffect(() => {
    const hub = createRefreshHub(async () => {
      const nextQueue = await fetchReviewQueueData();
      useQueueStore.setState({
        items: nextQueue.items,
        summary: nextQueue.summary,
      });
      return nextQueue;
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
