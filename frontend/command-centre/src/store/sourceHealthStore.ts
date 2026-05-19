import { create } from "zustand";
import { provinceDistribution } from "../data/harvestedRfqs";

const nowIso = () => new Date().toISOString();

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
    lastUpdatedAt: nowIso(),
  }));

const buildSourceSummary = (sources) => ({
  totalSources: sources.length,
  activeSources: sources.filter((item) => item.active).length,
  healthySources: sources.filter((item) => item.status === "healthy").length,
  degradedSources: sources.filter((item) => item.status === "degraded").length,
  failingSources: sources.filter((item) => item.status === "watch").length,
  disabledSources: sources.filter((item) => !item.active).length,
  parserFailureRate: sources.length ? Math.round((sources.reduce((total, item) => total + Number(item.parserFailureRate || 0), 0) / sources.length) * 10000) / 10000 : 0,
  averageResponseTimeMs: 0,
  recentSourceFailures: sources.filter((item) => item.failureCount > 0).map((item) => ({
    sourceId: item.id,
    name: item.name,
    status: item.status,
    failureCount: item.failureCount,
    consecutiveFailures: item.failureCount,
    parserFailureRate: item.parserFailureRate,
  })),
  generatedAt: nowIso(),
  dataSource: "static_seed",
  status: "runtime_fallback",
});

const useSourceHealthStore = create((set, get) => ({
  sources: buildSourceHealth(),
  summary: buildSourceSummary(buildSourceHealth()),
  loading: false,
  refreshing: false,
  stale: false,
  error: "",
  dataSource: "static_seed",
  lastUpdatedAt: nowIso(),
  setSourceHealthSnapshot: (snapshot = {}) => {
    const sources = snapshot.sources || buildSourceHealth();
    set({
      sources,
      summary: snapshot.summary || buildSourceSummary(sources),
      loading: false,
      refreshing: false,
      stale: snapshot.dataSource && snapshot.dataSource !== "runtime" ? true : false,
      error: "",
      dataSource: snapshot.dataSource || "runtime_fallback",
      lastUpdatedAt: snapshot.generatedAt || nowIso(),
    });
  },
  refreshSourceHealth: () => {
    const sources = buildSourceHealth();
    set({
      sources,
      summary: buildSourceSummary(sources),
      loading: false,
      refreshing: false,
      stale: false,
      error: "",
      dataSource: "static_seed",
      lastUpdatedAt: nowIso(),
    });
  },
  getSourceHealthSnapshot: () => ({
    sources: get().sources,
    summary: get().summary,
    loading: get().loading,
    refreshing: get().refreshing,
    stale: get().stale,
    error: get().error,
    dataSource: get().dataSource,
    lastUpdatedAt: get().lastUpdatedAt,
  }),
}));

export default useSourceHealthStore;
