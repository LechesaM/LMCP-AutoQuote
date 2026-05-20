import { useEffect, useMemo, useState } from "react";
import { fetchEvidenceAccelerationData, fetchFocusSessionsData, fetchReviewEfficiencyData } from "../api/reviewEfficiencyClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
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
};

export function useReviewEfficiency({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const [reviewEfficiency, focusSessions, evidenceAcceleration] = await Promise.all([
          fetchReviewEfficiencyData(),
          fetchFocusSessionsData(),
          fetchEvidenceAccelerationData(),
        ]);
        if (active) {
          setState({
            ...initialState,
            loading: false,
            refreshing: false,
            error: "",
            stale: reviewEfficiency.dataSource !== "runtime",
            dataSource: reviewEfficiency.dataSource,
            lastUpdated: reviewEfficiency.generatedAt || new Date().toISOString(),
            reviewEfficiency,
            focusSessions,
            evidenceAcceleration,
          });
        }
      } catch (exception) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: exception instanceof Error ? exception.message : "Unable to load review efficiency",
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
        const [reviewEfficiency, focusSessions, evidenceAcceleration] = await Promise.all([
          fetchReviewEfficiencyData(),
          fetchFocusSessionsData(),
          fetchEvidenceAccelerationData(),
        ]);
        setState({
          ...initialState,
          loading: false,
          refreshing: false,
          error: "",
          stale: reviewEfficiency.dataSource !== "runtime",
          dataSource: reviewEfficiency.dataSource,
          lastUpdated: reviewEfficiency.generatedAt || new Date().toISOString(),
          reviewEfficiency,
          focusSessions,
          evidenceAcceleration,
        });
        return reviewEfficiency;
      },
    }),
    [state],
  );
}

export default useReviewEfficiency;

