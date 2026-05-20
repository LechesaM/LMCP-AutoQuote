import { useEffect, useMemo, useState } from "react";
import { fetchQueueHeatmapData, fetchReviewPrioritiesData, fetchReviewQueueOptimizationData } from "../api/reviewQueueOptimizationClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
  queueOptimization: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    optimizedQueue: [],
    priorityGroups: { urgent: [], high: [], medium: [], low: [] },
    overdueReviews: [],
    staleRfqs: [],
    overloadedQueue: false,
    summary: { total: 0, urgent: 0, high: 0, medium: 0, low: 0, averagePriorityScore: 0, averageQueueAgeMinutes: 0 },
  },
  queueHeatmap: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    heatmap: [],
    operatorDistribution: {},
    sourceDistribution: {},
    escalationDensity: {},
    provinceDensity: {},
  },
  reviewPriorities: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    priorityScore: 0,
    priorityGroups: { urgent: [], high: [], medium: [], low: [] },
    escalationRecommendations: [],
    reviewUrgency: "normal",
    overloadedQueue: false,
  },
};

export function useQueueOptimization({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const [queueOptimization, queueHeatmap, reviewPriorities] = await Promise.all([
          fetchReviewQueueOptimizationData(),
          fetchQueueHeatmapData(),
          fetchReviewPrioritiesData(),
        ]);
        if (active) {
          setState({
            ...initialState,
            loading: false,
            refreshing: false,
            error: "",
            stale: queueOptimization.dataSource !== "runtime",
            dataSource: queueOptimization.dataSource,
            lastUpdated: queueOptimization.generatedAt || new Date().toISOString(),
            queueOptimization,
            queueHeatmap,
            reviewPriorities,
          });
        }
      } catch (exception) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: exception instanceof Error ? exception.message : "Unable to load queue optimization",
            stale: true,
          }));
        }
      }
    };
    load();
    const timer = window.setInterval(() => {
      load().catch(() => {});
    }, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return useMemo(
    () => ({
      ...state,
      refresh: async () => {
        const [queueOptimization, queueHeatmap, reviewPriorities] = await Promise.all([
          fetchReviewQueueOptimizationData(),
          fetchQueueHeatmapData(),
          fetchReviewPrioritiesData(),
        ]);
        setState({
          ...initialState,
          loading: false,
          refreshing: false,
          error: "",
          stale: queueOptimization.dataSource !== "runtime",
          dataSource: queueOptimization.dataSource,
          lastUpdated: queueOptimization.generatedAt || new Date().toISOString(),
          queueOptimization,
          queueHeatmap,
          reviewPriorities,
        });
        return queueOptimization;
      },
    }),
    [state],
  );
}

export default useQueueOptimization;

