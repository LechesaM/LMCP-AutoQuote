import { useEffect, useState } from "react";
import { fetchOperatorActions, postOperatorAction } from "../api/operatorActionsClient";

const initialState = {
  loading: true,
  refreshing: false,
  error: "",
  dataSource: "static_seed",
  generatedAt: "",
  actions: [],
  total: 0,
};

function buildActionPath(action) {
  const mapping = {
    assign_operator: "/operator/action/assign",
    mark_reviewed: "/operator/action/reviewed",
    request_clarification: "/operator/action/request-clarification",
    archive_rfq: "/operator/action/archive",
    mark_evidence_incomplete: "/operator/action/request-clarification",
    mark_supplier_quote_received: "/operator/action/reviewed",
    mark_waiting_pricing: "/operator/action/request-clarification",
    escalate_review: "/operator/action/escalate",
    reopen_review: "/operator/action/request-clarification",
    acknowledge_alert: "/operator/action/acknowledge-alert",
  };
  return mapping[action] || "/operator/action/reviewed";
}

export function useOperatorActions({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setState((current) => ({ ...current, refreshing: true, loading: current.generatedAt === "", error: "" }));
      try {
        const next = await fetchOperatorActions();
        if (active) {
          setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
        }
      } catch (error) {
        if (active) {
          setState((current) => ({
            ...current,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "Unable to load operator actions",
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
      const next = await fetchOperatorActions();
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
      return next;
    },
    performAction: async (action, payload) => {
      const response = await postOperatorAction(buildActionPath(action), {
        action,
        operator_id: payload.operatorId,
        tender_id: payload.tenderId,
        target_type: payload.targetType || "rfq",
        note: payload.note || "",
        details: payload.details || {},
      });
      const next = await fetchOperatorActions();
      setState({ ...initialState, loading: false, refreshing: false, error: "", ...next });
      return response;
    },
  };
}

export default useOperatorActions;
