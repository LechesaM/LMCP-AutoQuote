import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildPipelineMetrics,
  fetchAutonomousStatus,
  fetchOpportunities,
  fetchPipelineHealth,
  fetchSummary,
} from "../services/pipelineActivityApi";

const DEFAULT_POLL_INTERVAL = 15000;

export function usePipelineActivity(pollInterval = DEFAULT_POLL_INTERVAL) {
  const [health, setHealth] = useState(null);
  const [healthEndpoint, setHealthEndpoint] = useState(null);
  const [summary, setSummary] = useState(null);
  const [autonomousStatus, setAutonomousStatus] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [opportunityEndpoint, setOpportunityEndpoint] = useState(null);
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
      const [healthResult, summaryResult, autonomousResult, opportunitiesResult] =
        await Promise.all([
          fetchPipelineHealth(),
          fetchSummary(),
          fetchAutonomousStatus(),
          fetchOpportunities(),
        ]);

      setHealth(healthResult.data || null);
      setHealthEndpoint(healthResult.endpoint || null);
      setSummary(summaryResult || null);
      setAutonomousStatus(autonomousResult || null);
      setOpportunities(opportunitiesResult.items || []);
      setOpportunityEndpoint(opportunitiesResult.endpoint || null);
      setError("");
    } catch (err) {
      setError(err?.message || "Failed to load pipeline activity.");
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

  const metrics = useMemo(
    () => buildPipelineMetrics(opportunities),
    [opportunities]
  );

  return {
    health,
    healthEndpoint,
    summary,
    autonomousStatus,
    opportunities,
    opportunityEndpoint,
    loading,
    refreshing,
    error,
    metrics,
    refresh: () => load(true),
  };
}
