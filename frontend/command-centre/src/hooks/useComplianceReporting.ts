import { useEffect, useMemo, useState } from "react";
import { fetchComplianceReportingSnapshot } from "../api/complianceReportingClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
  status: "runtime_fallback",
  complianceReport: {},
  exportBundle: {},
  attestation: {},
  policyAcknowledgements: {},
  legalHolds: {},
  accessReview: {},
};

export function useComplianceReporting({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const next = await fetchComplianceReportingSnapshot();
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
            error: exception instanceof Error ? exception.message : "Unable to load compliance reporting snapshot",
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
        const next = await fetchComplianceReportingSnapshot();
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

export default useComplianceReporting;

