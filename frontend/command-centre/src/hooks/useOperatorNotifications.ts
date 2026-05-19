import { useEffect, useState } from "react";
import { fetchOperatorNotifications } from "../api/operatorNotificationsClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  dataSource: "static_seed",
  generatedAt: "",
  notifications: [],
};

export function useOperatorNotifications({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchOperatorNotifications();
        if (active) {
          setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load operator notifications",
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
      const next = await fetchOperatorNotifications();
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
      return next;
    },
  };
}

export default useOperatorNotifications;
