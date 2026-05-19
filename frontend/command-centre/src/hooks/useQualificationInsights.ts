import { useEffect, useState } from "react";
import { fetchQualificationInsights } from "../api/qualificationInsightsClient";

export function useQualificationInsights({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState({ loading: true, refreshing: false, error: "", dataSource: "static_seed", generatedAt: "", summary: {}, provinceHeat: {}, lowConfidenceRfqs: [], riskDistribution: {}, qualificationScoreAverage: 0, riskScoreAverage: 0, topRejectionReasons: [], topManualReviewTriggers: [], goCount: 0, manualReviewCount: 0, rejectCount: 0 });

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchQualificationInsights();
        if (active) {
          setState({
            loading: false,
            refreshing: false,
            error: "",
            ...next,
          });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load qualification insights",
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

  return {
    ...state,
    refresh: async () => {
      const next = await fetchQualificationInsights();
      setState({ loading: false, refreshing: false, error: "", ...next });
    },
  };
}
