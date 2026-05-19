import { useEffect, useState } from "react";
import { fetchOperatorCapacity } from "../api/operatorAssignmentsClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  dataSource: "static_seed",
  generatedAt: "",
  status: "ok",
  teamSize: 10,
  perOperatorDailyCapacity: 100,
  totalDailyCapacity: 1000,
  assignedToday: 0,
  remainingCapacity: 1000,
  overloaded: false,
  recommendedLoad: 0,
};

export function useOperatorCapacity({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchOperatorCapacity();
        if (active) {
          setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load operator capacity",
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
    total: state.totalDailyCapacity,
    used: state.assignedToday,
    remaining: state.remainingCapacity,
    utilization: state.totalDailyCapacity ? Math.round((state.assignedToday / state.totalDailyCapacity) * 1000) / 10 : 0,
    refresh: async () => {
      const next = await fetchOperatorCapacity();
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
      return next;
    },
  };
}

export default useOperatorCapacity;
