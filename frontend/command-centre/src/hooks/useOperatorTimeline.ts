import { useEffect, useState } from "react";
import { fetchOperatorTimeline } from "../api/operatorTimelineClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  dataSource: "static_seed",
  generatedAt: "",
  events: [],
  total: 0,
};

export function useOperatorTimeline({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchOperatorTimeline();
        if (active) {
          setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load operator timeline",
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
      const next = await fetchOperatorTimeline();
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
      return next;
    },
  };
}

export default useOperatorTimeline;
