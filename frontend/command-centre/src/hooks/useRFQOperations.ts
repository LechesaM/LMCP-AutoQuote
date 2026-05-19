import { useEffect, useState } from "react";
import { fetchRFQDetail, fetchRFQOperations } from "../api/rfqOperationsClient";

export function useRFQOperations({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState({ loading: true, refreshing: false, error: "", dataSource: "static_seed", generatedAt: "", summary: { total: 0, go: 0, manualReview: 0, reject: 0, dataSource: "static_seed" }, rows: [] });

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.rows.length === 0, error: "" }));
      try {
        const next = await fetchRFQOperations();
        if (active) {
          setState({
            loading: false,
            refreshing: false,
            error: "",
            dataSource: next.dataSource || "static_seed",
            generatedAt: next.generatedAt || new Date().toISOString(),
            summary: next.summary || { total: 0, go: 0, manualReview: 0, reject: 0, dataSource: "static_seed" },
            rows: next.rows || [],
          });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load RFQ operations",
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
      const next = await fetchRFQOperations();
      setState({
        loading: false,
        refreshing: false,
        error: "",
        dataSource: next.dataSource || "static_seed",
        generatedAt: next.generatedAt || new Date().toISOString(),
        summary: next.summary || { total: 0, go: 0, manualReview: 0, reject: 0, dataSource: "static_seed" },
        rows: next.rows || [],
      });
    },
    getDetail: fetchRFQDetail,
  };
}
