import { create } from "zustand";
import { provinceDistribution } from "../data/harvestedRfqs";

const buildSourceHealth = () =>
  provinceDistribution.map((row) => ({
    id: row.code,
    name: row.province,
    tier: row.rfqs > 150 ? "Tier 1" : row.rfqs > 80 ? "Tier 2" : "Tier 3",
    active: row.eligible > 20,
    eligible: row.eligible,
    total: row.rfqs,
    status: row.eligible > 40 ? "healthy" : row.eligible > 25 ? "degraded" : "watch",
    failureCount: row.eligible > 40 ? 0 : row.eligible > 25 ? 1 : 2,
    parserFailureRate: row.eligible > 40 ? 0 : row.eligible > 25 ? 0.07 : 0.14,
    evidenceStale: row.eligible < 30,
    lastUpdatedAt: new Date().toISOString(),
  }));

const useSourceHealthStore = create((set, get) => ({
  sources: buildSourceHealth(),
  refreshSourceHealth: () => set({ sources: buildSourceHealth() }),
  getSourceHealthSnapshot: () => get().sources,
}));

export default useSourceHealthStore;
