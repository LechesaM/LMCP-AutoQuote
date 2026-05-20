import { useEffect, useMemo, useState } from "react";
import { fetchAuditDefensibilitySnapshot } from "../api/auditDefensibilityClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
  status: "runtime_fallback",
  auditIntegrity: {},
  accessReview: {},
  legalHolds: {},
  retention: {},
  regulatoryExport: {},
  evidenceChain: {},
};

export function useAuditDefensibility({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const next = await fetchAuditDefensibilitySnapshot();
        if (active) {
          setState({
            ...initialState,
            ...next,
            loading: false,
            refreshing: false,
            error: "",
            stale: next.dataSource !== "runtime",
            lastUpdated: next.generatedAt || new Date().toISOString(),
          });
        }
      } catch (exception) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: exception instanceof Error ? exception.message : "Unable to load audit defensibility snapshot",
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
        const next = await fetchAuditDefensibilitySnapshot();
        setState({
          ...initialState,
          ...next,
          loading: false,
          refreshing: false,
          error: "",
          stale: next.dataSource !== "runtime",
          lastUpdated: next.generatedAt || new Date().toISOString(),
        });
        return next;
      },
    }),
    [state],
  );
}

export default useAuditDefensibility;

