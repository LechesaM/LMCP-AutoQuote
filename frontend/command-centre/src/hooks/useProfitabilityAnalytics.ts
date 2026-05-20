import { useEffect, useMemo, useState } from "react";
import { fetchProfitabilityAnalytics } from "../api/profitabilityAnalyticsClient";

export function useProfitabilityAnalytics({ intervalMs = 30000 } = {}) {
  const [snapshot, setSnapshot] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setRefreshing(true);
    try {
      const next = await fetchProfitabilityAnalytics();
      setSnapshot(next);
      setError("");
      return next;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Unable to refresh profitability analytics");
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
      summary: snapshot?.summary || {},
      estimatedRfqProfitability: snapshot?.estimatedRfqProfitability || [],
      estimatedMarginDistribution: snapshot?.estimatedMarginDistribution || {},
      highValueRfqs: snapshot?.highValueRfqs || [],
      lowConfidenceProfitability: snapshot?.lowConfidenceProfitability || [],
      stalePricingImpact: snapshot?.stalePricingImpact || [],
      supplierEvidenceImpact: snapshot?.supplierEvidenceImpact || [],
      profitabilityBySource: snapshot?.profitabilityBySource || [],
      profitabilityByProvince: snapshot?.profitabilityByProvince || [],
      refresh,
    }),
    [snapshot, loading, refreshing, error],
  );
}

