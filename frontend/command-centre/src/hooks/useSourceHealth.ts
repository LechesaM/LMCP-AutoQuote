import { useEffect, useState } from "react";
import { fetchSourceHealthDetails } from "../api/sourceHealthDetailClient";

export function useSourceHealth({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState({ loading: true, refreshing: false, error: "", dataSource: "static_seed", generatedAt: "", rows: [], tierBreakdown: {}, summary: { totalSources: 0, healthySources: 0, degradedSources: 0, failingSources: 0, disabledSources: 0 } });

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchSourceHealthDetails();
        if (active) {
          setState({ loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load source health",
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
      const next = await fetchSourceHealthDetails();
      setState({ loading: false, refreshing: false, error: "", ...next });
    },
  };
}
