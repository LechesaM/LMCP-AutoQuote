import { useEffect, useMemo, useState } from "react";
import { fetchOperatorProductivitySnapshot } from "../api/operatorProductivityClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
  workload: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    teamSize: 10,
    totalDailyCapacity: 1000,
    assignedToday: 0,
    remainingCapacity: 1000,
    averageUtilization: 0,
    averageWorkloadScore: 0,
    overloadWarnings: [],
    underutilizationWarnings: [],
    operators: [],
  },
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
  reviewEfficiency: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    rfqsReviewedPerHour: 0,
    reviewCompletionTimeMinutes: 0,
    evidenceHandlingTimeMinutes: 0,
    escalationFrequency: 0,
    reassignmentFrequency: 0,
    queueAgingTrends: {},
    operatorThroughputTrends: {},
    timelineGapMinutes: 0,
    throughputBottlenecks: [],
    advisoryOnly: true,
  },
  focusSessions: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    sessions: [],
    summary: {},
    advisoryOnly: true,
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
  evidenceAcceleration: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    missingEvidence: [],
    staleEvidence: [],
    supplierQuoteCompleteness: [],
    pricingMismatchSummary: [],
    groupedWarnings: {},
    summary: {},
  },
  shortcuts: {
    status: "runtime_fallback",
    generatedAt: "",
    dataSource: "runtime_fallback",
    shortcuts: [],
    quickActions: [],
    filterPresets: [],
    advisoryOnly: true,
  },
};

export function useOperatorProductivity({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const next = await fetchOperatorProductivitySnapshot();
        if (active) {
          setState({
            ...initialState,
            loading: false,
            refreshing: false,
            error: "",
            stale: next.dataSource !== "runtime",
            ...next,
            lastUpdated: next.generatedAt || new Date().toISOString(),
          });
        }
      } catch (exception) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: exception instanceof Error ? exception.message : "Unable to load productivity snapshot",
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
        const next = await fetchOperatorProductivitySnapshot();
        setState({
          ...initialState,
          loading: false,
          refreshing: false,
          error: "",
          stale: next.dataSource !== "runtime",
          ...next,
          lastUpdated: next.generatedAt || new Date().toISOString(),
        });
        return next;
      },
    }),
    [state],
  );
}

export default useOperatorProductivity;

