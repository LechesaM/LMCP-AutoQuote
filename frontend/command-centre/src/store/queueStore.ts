import { create } from "zustand";
import { recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";

const buildQueueItems = () =>
  topHighProfitRfqs.map((item, index) => ({
    id: `${item.title}-${index}`,
    title: item.title,
    province: item.province,
    value: item.value,
    profit: item.profit,
    recommendation: index === 0 ? "GO" : "MANUAL_REVIEW",
  }));

const useQueueStore = create((set, get) => ({
  items: buildQueueItems(),
  summary: {
    total: buildQueueItems().length,
    goCount: buildQueueItems().filter((item) => item.recommendation === "GO").length,
    manualCount: buildQueueItems().filter((item) => item.recommendation === "MANUAL_REVIEW").length,
    alerts: recentAlerts,
    lagItems: buildQueueItems().filter((item) => item.recommendation !== "GO").length,
    lastRefreshedAt: new Date().toISOString(),
  },
  refreshQueue: () =>
    set({
      items: buildQueueItems(),
      summary: {
        total: buildQueueItems().length,
        goCount: buildQueueItems().filter((item) => item.recommendation === "GO").length,
        manualCount: buildQueueItems().filter((item) => item.recommendation === "MANUAL_REVIEW").length,
        alerts: recentAlerts,
        lagItems: buildQueueItems().filter((item) => item.recommendation !== "GO").length,
        lastRefreshedAt: new Date().toISOString(),
      },
    }),
  getQueueSnapshot: () => ({
    items: get().items,
    summary: get().summary,
  }),
}));

export default useQueueStore;
