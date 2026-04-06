import { useEffect, useState } from "react";
import { endpoints } from "../config/endpoints";
import { apiGet } from "../services/api";
import {
  fallbackAlerts,
  fallbackPortals,
  fallbackSummary,
  fallbackTenders,
} from "../data/fallbackData";

export function useDashboardData() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(fallbackSummary);
  const [tenders, setTenders] = useState(fallbackTenders);
  const [portals, setPortals] = useState(fallbackPortals);
  const [alerts, setAlerts] = useState(fallbackAlerts);

  const refresh = async () => {
    setLoading(true);

    const [summaryData, tenderData, portalData, alertData] = await Promise.all([
      apiGet(endpoints.summary).catch(() => fallbackSummary),
      apiGet(endpoints.opportunities).catch(() => fallbackTenders),
      apiGet(endpoints.portalHealth).catch(() => fallbackPortals),
      apiGet(endpoints.alerts).catch(() => fallbackAlerts),
    ]);

    setSummary(summaryData);
    setTenders(Array.isArray(tenderData) ? tenderData : fallbackTenders);
    setPortals(Array.isArray(portalData) ? portalData : fallbackPortals);
    setAlerts(Array.isArray(alertData) ? alertData : fallbackAlerts);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  return {
    loading,
    summary,
    tenders,
    portals,
    alerts,
    refresh,
  };
}
