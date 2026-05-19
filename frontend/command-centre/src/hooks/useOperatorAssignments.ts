import { useEffect, useState } from "react";
import { fetchOperatorAssignments, fetchOperatorCapacity } from "../api/operatorAssignmentsClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  dataSource: "static_seed",
  generatedAt: "",
  assignments: [],
  recommendations: [],
  summary: { totalAssignments: 0, activeAssignments: 0, operators: 10, capacity: 1000 },
  capacity: {
    status: "ok",
    generatedAt: "",
    dataSource: "static_seed",
    teamSize: 10,
    perOperatorDailyCapacity: 100,
    totalDailyCapacity: 1000,
    assignedToday: 0,
    remainingCapacity: 1000,
    overloaded: false,
    recommendedLoad: 0,
  },
};

export function useOperatorAssignments({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const [nextAssignments, nextCapacity] = await Promise.all([fetchOperatorAssignments(), fetchOperatorCapacity()]);
        if (active) {
          setState({
            ...initialState,
            loading: false,
            refreshing: false,
            error: "",
            ...nextAssignments,
            capacity: nextCapacity,
          });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load operator assignments",
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
      const [nextAssignments, nextCapacity] = await Promise.all([fetchOperatorAssignments(), fetchOperatorCapacity()]);
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...nextAssignments, capacity: nextCapacity });
      return nextAssignments;
    },
  };
}

export default useOperatorAssignments;
