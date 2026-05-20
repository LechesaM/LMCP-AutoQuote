import { create } from "zustand";
import { commandMetrics, opportunityBreakdown, provinceDistribution, recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";
import { pickTelemetrySnapshot, sameTelemetrySnapshot, sameTelemetryStatus } from "./telemetryGuards.js";

const nowIso = () => new Date().toISOString();

const useTelemetryStore = create((set, get) => ({
  commandMetrics,
  opportunityBreakdown,
  provinceDistribution,
  recentAlerts,
  topHighProfitRfqs,
  loading: false,
  refreshing: false,
  stale: false,
  error: "",
  dataSource: "static_seed",
  lastRefreshedAt: nowIso(),
  currentRoute: "/dashboard",
  currentRouteLabel: "Dashboard",
  routeViewCount: 0,
  lastRouteAt: nowIso(),
  routeHistory: [],
  setTelemetrySnapshot: (snapshot = {}) =>
    set((state) => {
      const next = {
        ...state,
        commandMetrics: snapshot.commandMetrics || commandMetrics,
        opportunityBreakdown: snapshot.opportunityBreakdown || opportunityBreakdown,
        provinceDistribution: snapshot.provinceDistribution || provinceDistribution,
        recentAlerts: snapshot.recentAlerts || recentAlerts,
        topHighProfitRfqs: snapshot.topHighProfitRfqs || topHighProfitRfqs,
        loading: false,
        refreshing: false,
        stale: snapshot.dataSource && snapshot.dataSource !== "runtime" ? true : false,
        error: "",
        dataSource: snapshot.dataSource || "runtime_fallback",
        lastRefreshedAt: snapshot.generatedAt || nowIso(),
      };

      return sameTelemetrySnapshot(pickTelemetrySnapshot(state), pickTelemetrySnapshot(next)) ? state : next;
    }),
  setTelemetryStatus: (updates = {}) =>
    set((state) => {
      if (sameTelemetryStatus(state, updates)) {
        return state;
      }

      return { ...state, ...updates };
    }),
  recordRouteView: (pathname, label = pathname) =>
    set((state) => {
      const lastRoute = state.routeHistory[0];
      const now = Date.now();
      const lastSeenAt = state.lastRouteAt ? Date.parse(state.lastRouteAt) : 0;
      if (lastRoute?.pathname === pathname && state.currentRoute === pathname && Number.isFinite(lastSeenAt) && now - lastSeenAt < 500) {
        return state;
      }

      const event = {
        pathname,
        label,
        seenAt: new Date().toISOString(),
      };

      return {
        currentRoute: pathname,
        currentRouteLabel: label,
        routeViewCount: state.routeViewCount + 1,
        lastRouteAt: event.seenAt,
        routeHistory: [event, ...state.routeHistory].slice(0, 12),
      };
    }),
  refreshFromStaticData: () =>
    set({
      commandMetrics,
      opportunityBreakdown,
      provinceDistribution,
      recentAlerts,
      topHighProfitRfqs,
      loading: false,
      refreshing: false,
      stale: false,
      error: "",
      dataSource: "static_seed",
      lastRefreshedAt: nowIso(),
    }),
  getTelemetrySnapshot: () => ({
    commandMetrics: get().commandMetrics,
    opportunityBreakdown: get().opportunityBreakdown,
    provinceDistribution: get().provinceDistribution,
    recentAlerts: get().recentAlerts,
    topHighProfitRfqs: get().topHighProfitRfqs,
    loading: get().loading,
    refreshing: get().refreshing,
    stale: get().stale,
    error: get().error,
    dataSource: get().dataSource,
    lastRefreshedAt: get().lastRefreshedAt,
    currentRoute: get().currentRoute,
    currentRouteLabel: get().currentRouteLabel,
    routeViewCount: get().routeViewCount,
    lastRouteAt: get().lastRouteAt,
    routeHistory: get().routeHistory,
  }),
}));

export default useTelemetryStore;
