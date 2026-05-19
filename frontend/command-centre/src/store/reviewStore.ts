import { recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";

export function getReviewQueueItems() {
  return topHighProfitRfqs.map((item, index) => ({
    id: `${item.title}-${index}`,
    title: item.title,
    province: item.province,
    value: item.value,
    profit: item.profit,
    recommendation: index === 0 ? "GO" : "MANUAL_REVIEW",
  }));
}

export function getReviewSummary() {
  const items = getReviewQueueItems();
  return {
    total: items.length,
    goCount: items.filter((item) => item.recommendation === "GO").length,
    manualCount: items.filter((item) => item.recommendation === "MANUAL_REVIEW").length,
    alerts: recentAlerts,
  };
}
