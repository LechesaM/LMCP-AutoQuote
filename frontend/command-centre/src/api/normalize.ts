function numberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function stringOrEmpty(value) {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

export function normalizeDashboardTelemetry(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return {
    totalHarvested: numberOrZero(source.totalHarvested),
    eligibleRfqs: numberOrZero(source.eligibleRfqs),
    estimatedValue: numberOrZero(source.estimatedValue),
    avgMargin: numberOrZero(source.avgMargin),
    highProfitRfqs: numberOrZero(source.highProfitRfqs),
    avgEstimatedProfit: numberOrZero(source.avgEstimatedProfit),
    eligibleRate: numberOrZero(source.eligibleRate),
  };
}

export function normalizeReviewQueue(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  const items = Array.isArray(source.items) ? source.items : [];
  return {
    items: items.map((item, index) => ({
      id: stringOrEmpty(item?.id || `${item?.title || "item"}-${index}`),
      title: stringOrEmpty(item?.title),
      province: stringOrEmpty(item?.province),
      value: stringOrEmpty(item?.value),
      profit: stringOrEmpty(item?.profit),
      recommendation: stringOrEmpty(item?.recommendation || "MANUAL_REVIEW"),
    })),
    summary: {
      total: numberOrZero(source.summary?.total ?? items.length),
      goCount: numberOrZero(source.summary?.goCount),
      manualCount: numberOrZero(source.summary?.manualCount),
      alerts: Array.isArray(source.summary?.alerts) ? source.summary.alerts.map(stringOrEmpty) : [],
    },
  };
}

export function normalizeHarvestHealth(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  const sources = Array.isArray(source.sources) ? source.sources : [];
  return {
    status: stringOrEmpty(source.status || "advisory"),
    sources: sources.map((item, index) => ({
      id: stringOrEmpty(item?.id || `source-${index}`),
      name: stringOrEmpty(item?.name),
      tier: stringOrEmpty(item?.tier || "Tier 3"),
      active: Boolean(item?.active),
      eligible: numberOrZero(item?.eligible),
      total: numberOrZero(item?.total),
      status: stringOrEmpty(item?.status || "advisory"),
    })),
  };
}

export function normalizeQualificationSummary(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  return {
    manualGovernanceOnly: Boolean(source.manualGovernanceOnly),
    reviewReadyRequired: Boolean(source.reviewReadyRequired),
    proofCaptureRequired: Boolean(source.proofCaptureRequired),
  };
}
