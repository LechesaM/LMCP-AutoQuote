import { useEffect, useMemo, useState } from "react";
import { fetchExecutiveAnalytics } from "../api/executiveAnalyticsClient";

export function useExecutiveAnalytics({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchExecutiveAnalytics();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh executive analytics");
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    let active = true;
    const tick = async () => {
      if (!active) return;
      await refresh();
    };
    tick();
    const timer = window.setInterval(() => {
      tick().catch(() => {});
    }, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return useMemo(
    () => ({
      loading,
      refreshing,
      error,
      stale: Boolean(error) || (snapshot?.dataSource || "runtime_fallback") !== "runtime",
      dataSource: snapshot?.dataSource || "runtime_fallback",
      lastUpdated: snapshot?.generatedAt || "",
      executiveSummary: snapshot?.executiveSummary || {},
      weeklyTrend: snapshot?.weeklyTrend || [],
      monthlyTrend: snapshot?.monthlyTrend || [],
      rollingAverages: snapshot?.rollingAverages || {},
      profitability: snapshot?.profitability || {},
      rfqConversion: snapshot?.rfqConversion || {},
      sourceROI: snapshot?.sourceROI || {},
      operatorTrends: snapshot?.operatorTrends || {},
      governanceTrends: snapshot?.governanceTrends || {},
      workloadForecast: snapshot?.workloadForecast || {},
      opportunityForecast: snapshot?.opportunityForecast || {},
      revenueProjection: snapshot?.revenueProjection || {},
      historicalTrends: snapshot?.historicalTrends || {},
      productivity: snapshot?.productivity || {},
      sourceReliability: snapshot?.sourceReliability || {},
      sla: snapshot?.sla || {},
      runtimeMetrics: snapshot?.runtimeMetrics || {},
      workflowSummary: snapshot?.workflowSummary || {},
      pilotReadiness: snapshot?.pilotReadiness || {},
      tenderSuccessAnalytics: snapshot?.tenderSuccessAnalytics || {},
      observabilitySummary: snapshot?.observabilitySummary || {},
      strategicHighlights: snapshot?.strategicHighlights || [],
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}

