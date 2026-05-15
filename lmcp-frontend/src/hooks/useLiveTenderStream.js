import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchAutonomousStatus,
  fetchDashboardSummary,
  fetchLiveTenderStream,
} from "../services/liveTenderApi";

const DEFAULT_POLL_INTERVAL = 15000;

export function useLiveTenderStream(pollInterval = DEFAULT_POLL_INTERVAL) {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [sourceEndpoint, setSourceEndpoint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (silent = false) => {
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [stream, autonomousStatus, dashboardSummary] = await Promise.all([
        fetchLiveTenderStream(),
        fetchAutonomousStatus(),
        fetchDashboardSummary(),
      ]);

      setItems(stream.items || []);
      setSourceEndpoint(stream.sourceEndpoint || null);
      setStatus(autonomousStatus || null);
      setSummary(dashboardSummary || null);
      setError("");
    } catch (err) {
      setError(err?.message || "Failed to load live tender stream.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load(false);
    const timer = window.setInterval(() => load(true), pollInterval);
    return () => window.clearInterval(timer);
  }, [load, pollInterval]);

  const metrics = useMemo(() => {
    const total = items.length;
    const emailOnly = items.filter((x) =>
      String(x.submissionMethod).toLowerCase().includes("email")
    ).length;
    const portalOnly = items.filter((x) =>
      String(x.submissionMethod).toLowerCase().includes("portal")
    ).length;
    const highScore = items.filter((x) => Number(x.score || 0) >= 70).length;

    return { total, emailOnly, portalOnly, highScore };
  }, [items]);

  return {
    items,
    status,
    summary,
    sourceEndpoint,
    loading,
    refreshing,
    error,
    metrics,
    refresh: () => load(true),
  };
}
