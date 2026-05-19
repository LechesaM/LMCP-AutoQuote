import { create } from "zustand";
import { recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";

const nowIso = () => new Date().toISOString();

const buildQueueItems = () =>
  topHighProfitRfqs.map((item, index) => ({
    id: `${item.title}-${index}`,
    title: item.title,
    province: item.province,
    value: item.value,
    profit: item.profit,
    recommendation: index === 0 ? "GO" : "MANUAL_REVIEW",
  }));

const buildQueueSummary = (items) => ({
  total: items.length,
  goCount: items.filter((item) => item.recommendation === "GO").length,
  manualCount: items.filter((item) => item.recommendation === "MANUAL_REVIEW").length,
  alerts: recentAlerts,
  lagItems: items.filter((item) => item.recommendation !== "GO").length,
  pendingReviews: items.filter((item) => item.recommendation !== "GO").length,
  approvedToday: items.filter((item) => item.recommendation === "GO").length,
  manualReviewRequired: items.filter((item) => item.recommendation === "MANUAL_REVIEW").length,
  blockedReviews: 0,
  overdueReviews: 0,
  operatorCapacity: 1000,
  operatorCapacityUsed: items.length,
  operatorCapacityRemaining: Math.max(0, 1000 - items.length),
  queueLagMinutes: items.filter((item) => item.recommendation !== "GO").length * 15,
  lastRefreshedAt: nowIso(),
  generatedAt: nowIso(),
  dataSource: "static_seed",
  status: "runtime_fallback",
});

const useQueueStore = create((set, get) => ({
  items: buildQueueItems(),
  summary: buildQueueSummary(buildQueueItems()),
  loading: false,
  refreshing: false,
  stale: false,
  error: "",
  dataSource: "static_seed",
  lastRefreshedAt: nowIso(),
  setQueueSnapshot: (snapshot = {}) => {
    const items = snapshot.items || buildQueueItems();
    set({
      items,
      summary: snapshot.summary || buildQueueSummary(items),
      loading: false,
      refreshing: false,
      stale: snapshot.dataSource && snapshot.dataSource !== "runtime" ? true : false,
      error: "",
      dataSource: snapshot.dataSource || "runtime_fallback",
      lastRefreshedAt: snapshot.generatedAt || nowIso(),
    });
  },
  refreshQueue: () => {
    const items = buildQueueItems();
    set({
      items,
      summary: buildQueueSummary(items),
      loading: false,
      refreshing: false,
      stale: false,
      error: "",
      dataSource: "static_seed",
      lastRefreshedAt: nowIso(),
    });
  },
  getQueueSnapshot: () => ({
    items: get().items,
    summary: get().summary,
    loading: get().loading,
    refreshing: get().refreshing,
    stale: get().stale,
    error: get().error,
    dataSource: get().dataSource,
    lastRefreshedAt: get().lastRefreshedAt,
  }),
}));

export default useQueueStore;
