import { create } from "zustand";
import { commandMetrics, opportunityBreakdown, provinceDistribution, recentAlerts, topHighProfitRfqs } from "../data/harvestedRfqs";

const useTelemetryStore = create((set, get) => ({
  commandMetrics,
  opportunityBreakdown,
  provinceDistribution,
  recentAlerts,
  topHighProfitRfqs,
  lastRefreshedAt: new Date().toISOString(),
  currentRoute: "/dashboard",
  currentRouteLabel: "Dashboard",
  routeViewCount: 0,
  lastRouteAt: new Date().toISOString(),
  routeHistory: [],
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
      lastRefreshedAt: new Date().toISOString(),
    }),
  getTelemetrySnapshot: () => ({
    commandMetrics: get().commandMetrics,
    opportunityBreakdown: get().opportunityBreakdown,
    provinceDistribution: get().provinceDistribution,
    recentAlerts: get().recentAlerts,
    topHighProfitRfqs: get().topHighProfitRfqs,
    lastRefreshedAt: get().lastRefreshedAt,
    currentRoute: get().currentRoute,
    currentRouteLabel: get().currentRouteLabel,
    routeViewCount: get().routeViewCount,
    lastRouteAt: get().lastRouteAt,
    routeHistory: get().routeHistory,
  }),
}));

export default useTelemetryStore;
