import { useEffect, useMemo, useState } from "react";
import { fetchGovernanceComplianceSnapshot } from "../api/governanceComplianceClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  stale: false,
  dataSource: "runtime_fallback",
  lastUpdated: "",
  status: "runtime_fallback",
  policies: { summary: { policyCount: 0, categories: [], manualEnforcementOnly: true }, policies: [] },
  policyVersions: { policyVersions: [], supersededPolicies: [] },
  complianceControls: { controls: {}, warnings: [], blockers: [], complianceScore: 100, manualGovernanceOnly: true },
  accessReview: {},
  attestations: {},
  auditValidation: {},
  auditMonitor: {},
  auditSnapshot: {},
  retention: {},
  legalHolds: {},
  riskRegister: {},
  policyAcknowledgements: {},
  regulatoryExport: {},
};

export function useGovernanceCompliance({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.lastUpdated === "", error: "" }));
      try {
        const next = await fetchGovernanceComplianceSnapshot();
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
            error: exception instanceof Error ? exception.message : "Unable to load governance compliance snapshot",
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
        const next = await fetchGovernanceComplianceSnapshot();
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

export default useGovernanceCompliance;

