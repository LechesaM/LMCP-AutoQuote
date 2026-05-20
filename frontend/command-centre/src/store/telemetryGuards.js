const TELEMETRY_SNAPSHOT_FIELDS = [
  "commandMetrics",
  "opportunityBreakdown",
  "provinceDistribution",
  "recentAlerts",
  "topHighProfitRfqs",
  "loading",
  "refreshing",
  "stale",
  "error",
  "dataSource",
  "lastRefreshedAt",
];

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }
  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort()
      .reduce((acc, key) => {
        acc[key] = canonicalize(value[key]);
        return acc;
      }, {});
  }
  return value;
}

function stableSerialize(value) {
  try {
    return JSON.stringify(canonicalize(value));
  } catch {
    return "";
  }
}

export function pickTelemetrySnapshot(state = {}) {
  return TELEMETRY_SNAPSHOT_FIELDS.reduce((acc, key) => {
    acc[key] = state[key];
    return acc;
  }, {});
}

export function sameTelemetrySnapshot(current = {}, next = {}) {
  return stableSerialize(pickTelemetrySnapshot(current)) === stableSerialize(pickTelemetrySnapshot(next));
}

export function sameTelemetryStatus(current = {}, updates = {}) {
  const keys = Object.keys(updates || {});
  if (!keys.length) {
    return true;
  }

  return keys.every((key) => Object.is(current[key], updates[key]));
}

export function sameOperationalHealthSnapshot(current = {}, next = {}) {
  return stableSerialize({
    status: current.status,
    generatedAt: current.generatedAt,
    dataSource: current.dataSource,
    loading: current.loading,
    refreshing: current.refreshing,
    error: current.error,
    sourceFailures: current.sourceFailures,
    parserFailures: current.parserFailures,
    queueLag: current.queueLag,
    operatorCapacity: current.operatorCapacity,
    rfqAging: current.rfqAging,
    staleEvidence: current.staleEvidence,
    workflowFailures: current.workflowFailures,
    persistenceFailures: current.persistenceFailures,
    auditFailures: current.auditFailures,
  }) ===
    stableSerialize({
      status: next.status,
      generatedAt: next.generatedAt,
      dataSource: next.dataSource,
      loading: next.loading,
      refreshing: next.refreshing,
      error: next.error,
      sourceFailures: next.sourceFailures,
      parserFailures: next.parserFailures,
      queueLag: next.queueLag,
      operatorCapacity: next.operatorCapacity,
      rfqAging: next.rfqAging,
      staleEvidence: next.staleEvidence,
      workflowFailures: next.workflowFailures,
      persistenceFailures: next.persistenceFailures,
      auditFailures: next.auditFailures,
    });
}

export function sameRuntimeApiHealth(current = {}, next = {}) {
  return stableSerialize({
    status: current.status,
    dataSource: current.dataSource,
    error: current.error,
    latencyMs: current.latencyMs,
    lastCheckedAt: current.lastCheckedAt,
    route: current.route,
  }) ===
    stableSerialize({
      status: next.status,
      dataSource: next.dataSource,
      error: next.error,
      latencyMs: next.latencyMs,
      lastCheckedAt: next.lastCheckedAt,
      route: next.route,
    });
}

