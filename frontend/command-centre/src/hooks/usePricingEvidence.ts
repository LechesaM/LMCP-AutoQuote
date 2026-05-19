import { useEffect, useState } from "react";
import { fetchPricingEvidence } from "../api/pricingEvidenceClient";

export function usePricingEvidence({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState({ loading: true, refreshing: false, error: "", dataSource: "static_seed", generatedAt: "", summary: {}, pricingEvidenceRows: [], pricingAnomalies: [] });

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchPricingEvidence();
        if (active) {
          setState({ loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load pricing evidence",
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
      const next = await fetchPricingEvidence();
      setState({ loading: false, refreshing: false, error: "", ...next });
    },
  };
}
