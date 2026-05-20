import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchOperationalHealthData } from "../api/operationalHealthClient";
import useQueueStore from "../store/queueStore";
import useSourceHealthStore from "../store/sourceHealthStore";
import useTelemetryStore from "../store/telemetryStore";

function deriveLocalOperationalHealth({ sources, queueSummary, commandMetrics, recentAlerts, telemetryUpdatedAt }) {
  const sourceFailures = sources.filter((source) => source.status !== "healthy").length;
  const parserFailures = sources.filter((source) => Number(source.parserFailureRate || 0) > 0.1).length;
  const staleEvidence = sources.filter((source) => Boolean(source.evidenceStale)).length;
  const queueLag = Number(queueSummary.lagItems || 0);
  const operatorCapacityTotal = 1000;
  const operatorCapacityUsed = Number(queueSummary.total || 0);
  const operatorCapacityRemaining = Math.max(0, operatorCapacityTotal - operatorCapacityUsed);
  const operatorCapacityUtilization = operatorCapacityTotal
    ? Math.round((operatorCapacityUsed / operatorCapacityTotal) * 1000) / 10
    : 0;
  const rfqAging = Math.max(0, Number(commandMetrics.totalHarvested || 0) - Number(commandMetrics.eligibleRfqs || 0));
  const staleEvidenceSignals = staleEvidence + recentAlerts.filter((alert) => /update|soon|within 2 days|stale/i.test(String(alert))).length;
  const state =
    sourceFailures > 0 || parserFailures > 0
      ? "stale"
      : queueLag > 0 || staleEvidenceSignals > 0
        ? "refreshing"
        : "ready";

  return {
    state,
    sourceFailures,
    parserFailures,
    queueLag,
    operatorCapacity: {
      total: operatorCapacityTotal,
      used: operatorCapacityUsed,
      remaining: operatorCapacityRemaining,
      utilization: operatorCapacityUtilization,
    },
    rfqAging,
    staleEvidence: staleEvidenceSignals,
    queueLagLabel: queueLag > 0 ? "Backlog present" : "No lag detected",
    telemetryUpdatedAt,
    queueUpdatedAt: queueSummary.lastRefreshedAt || "",
    sourceHealthUpdatedAt: sources[0]?.lastUpdatedAt || "",
  };
}

export function useOperationalHealth() {
  const sources = useSourceHealthStore((state) => state.sources);
  const queueSummary = useQueueStore((state) => state.summary);
  const commandMetrics = useTelemetryStore((state) => state.commandMetrics);
  const recentAlerts = useTelemetryStore((state) => state.recentAlerts);
  const telemetryUpdatedAt = useTelemetryStore((state) => state.lastRefreshedAt);
  const [remoteHealth, setRemoteHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const activeRef = useRef(true);
  const remoteHealthRef = useRef(remoteHealth);
  const loadingRef = useRef(loading);
  const refreshingRef = useRef(refreshing);
  const errorRef = useRef(error);

  const commitRemoteHealth = useCallback((nextHealth) => {
    setRemoteHealth((current) => {
      if (current && nextHealth && JSON.stringify(current) === JSON.stringify(nextHealth)) {
        return current;
      }
      remoteHealthRef.current = nextHealth;
      return nextHealth;
    });
  }, []);

  const commitLoading = useCallback((nextValue) => {
    setLoading((current) => {
      if (current === nextValue) {
        return current;
      }
      loadingRef.current = nextValue;
      return nextValue;
    });
  }, []);

  const commitRefreshing = useCallback((nextValue) => {
    setRefreshing((current) => {
      if (current === nextValue) {
        return current;
      }
      refreshingRef.current = nextValue;
      return nextValue;
    });
  }, []);

  const commitError = useCallback((message) => {
    setError((current) => {
      if (current === message) {
        return current;
      }
      errorRef.current = message;
      return message;
    });
  }, []);

  const loadHealth = useCallback(async () => {
    if (!activeRef.current) {
      return null;
    }
    commitRefreshing(true);
    try {
      const nextHealth = await fetchOperationalHealthData();
      commitRemoteHealth(nextHealth);
      commitError("");
      return nextHealth;
    } catch (exception) {
      const message = exception instanceof Error ? exception.message : "Unable to refresh operational health";
      commitError(message);
      return null;
    } finally {
      commitLoading(false);
      commitRefreshing(false);
    }
  }, [commitError, commitLoading, commitRefreshing, commitRemoteHealth]);

  useEffect(() => {
    activeRef.current = true;
    loadHealth().catch(() => {});
    const timer = window.setInterval(() => {
      loadHealth().catch(() => {});
    }, 30000);
    return () => {
      activeRef.current = false;
      window.clearInterval(timer);
    };
  }, [loadHealth]);

  return useMemo(() => {
    const localHealth = deriveLocalOperationalHealth({
      sources,
      queueSummary,
      commandMetrics,
      recentAlerts,
      telemetryUpdatedAt,
    });
    const merged = remoteHealth
      ? {
          ...localHealth,
          state: remoteHealth.status === "healthy" ? "ready" : "stale",
          sourceFailures: remoteHealth.sourceFailures ?? localHealth.sourceFailures,
          parserFailures: remoteHealth.parserFailures ?? localHealth.parserFailures,
          queueLag: remoteHealth.queueLag ?? localHealth.queueLag,
          operatorCapacity: {
            ...localHealth.operatorCapacity,
            total: remoteHealth.operatorCapacity || localHealth.operatorCapacity.total,
          },
          rfqAging: remoteHealth.rfqAging ?? localHealth.rfqAging,
          staleEvidence: remoteHealth.staleEvidence ?? localHealth.staleEvidence,
          queueLagLabel: localHealth.queueLagLabel,
          telemetryUpdatedAt,
          queueUpdatedAt: queueSummary.lastRefreshedAt || "",
          sourceHealthUpdatedAt: sources[0]?.lastUpdatedAt || "",
          workflowFailures: remoteHealth.workflowFailures ?? 0,
          persistenceFailures: remoteHealth.persistenceFailures ?? 0,
          auditFailures: remoteHealth.auditFailures ?? 0,
          dataSource: remoteHealth.dataSource || "runtime_fallback",
          lastUpdated: remoteHealth.generatedAt || telemetryUpdatedAt,
          healthStatus: remoteHealth.status || "runtime_fallback",
        }
      : {
          ...localHealth,
          loading,
          refreshing,
          error,
          stale: true,
          dataSource: "static_seed",
          lastUpdated: telemetryUpdatedAt,
          healthStatus: "runtime_fallback",
          workflowFailures: 0,
          persistenceFailures: 0,
          auditFailures: 0,
        };

    return {
      ...merged,
      loading: loadingRef.current,
      refreshing: refreshingRef.current,
      error: errorRef.current,
      stale: Boolean(error) || merged.state !== "ready" || merged.dataSource !== "runtime",
      dataSource: merged.dataSource || "runtime_fallback",
      lastUpdated: merged.lastUpdated || telemetryUpdatedAt,
      refresh: loadHealth,
    };
  }, [sources, queueSummary, commandMetrics, recentAlerts, telemetryUpdatedAt, remoteHealth, loading, refreshing, error, loadHealth]);
}
