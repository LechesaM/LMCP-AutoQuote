function numberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringOrEmpty(value) {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

function arrayOrEmpty(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeProvinceDistribution(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row, index) => ({
    code: stringOrEmpty(row?.code || row?.province_code || `P${String(index).padStart(2, "0")}`),
    province: stringOrEmpty(row?.province),
    rfqs: numberOrZero(row?.rfqs),
    eligible: numberOrZero(row?.eligible),
    value: numberOrZero(row?.value),
    avgMargin: numberOrZero(row?.avgMargin ?? row?.avg_margin),
  }));
}

function normalizeOpportunityBreakdown(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row) => ({
    name: stringOrEmpty(row?.name),
    value: numberOrZero(row?.value),
  }));
}

function normalizeHighProfitRfqs(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row) => ({
    title: stringOrEmpty(row?.title),
    province: stringOrEmpty(row?.province),
    value: stringOrEmpty(row?.value),
    profit: stringOrEmpty(row?.profit),
  }));
}

export function normalizeDashboardTelemetry(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackMetrics = fallbackSource.commandMetrics || fallbackSource;
  const commandMetrics = {
    totalHarvested: numberOrZero(source.total_harvested_rfqs ?? source.totalHarvested ?? fallbackMetrics.totalHarvested),
    eligibleRfqs: numberOrZero(source.eligible_rfqs ?? source.eligibleRfqs ?? fallbackMetrics.eligibleRfqs),
    estimatedValue: numberOrZero(source.total_estimated_value ?? source.estimatedValue ?? fallbackMetrics.estimatedValue),
    highProfitRfqs: numberOrZero(source.high_profit_rfqs ?? source.highProfitRfqs ?? fallbackMetrics.highProfitRfqs),
    avgEstimatedProfit: numberOrZero(source.avg_estimated_profit ?? source.avgEstimatedProfit ?? fallbackMetrics.avgEstimatedProfit),
    avgMargin: numberOrZero(source.avg_margin ?? source.avgMargin ?? fallbackMetrics.avgMargin),
    eligibleRate: numberOrZero(source.eligible_rate ?? source.eligibleRate ?? fallbackMetrics.eligibleRate),
  };

  const provinceDistribution = normalizeProvinceDistribution(source.province_distribution ?? source.provinceDistribution, fallbackSource.provinceDistribution);
  const opportunityBreakdown = normalizeOpportunityBreakdown(source.opportunity_breakdown ?? source.opportunityBreakdown, fallbackSource.opportunityBreakdown);
  const topHighProfitRfqs = normalizeHighProfitRfqs(source.top_high_profit_rfqs ?? source.topHighProfitRfqs, fallbackSource.topHighProfitRfqs);
  const recentAlerts = arrayOrEmpty(source.recent_alerts ?? source.recentAlerts).length
    ? arrayOrEmpty(source.recent_alerts ?? source.recentAlerts).map(stringOrEmpty)
    : arrayOrEmpty(fallbackSource.recentAlerts).map(stringOrEmpty);

  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    commandMetrics,
    provinceDistribution,
    opportunityBreakdown,
    topHighProfitRfqs,
    recentAlerts,
    totalHarvested: commandMetrics.totalHarvested,
    eligibleRfqs: commandMetrics.eligibleRfqs,
    estimatedValue: commandMetrics.estimatedValue,
    avgMargin: commandMetrics.avgMargin,
    highProfitRfqs: commandMetrics.highProfitRfqs,
    avgEstimatedProfit: commandMetrics.avgEstimatedProfit,
    eligibleRate: commandMetrics.eligibleRate,
  };
}

export function normalizeReviewQueue(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const items = Array.isArray(source.items) && source.items.length ? source.items : arrayOrEmpty(fallbackSource.items);
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
      total: numberOrZero(source.summary?.total ?? source.pending_reviews ?? source.pendingReviews ?? fallbackSource.summary?.total ?? items.length),
      goCount: numberOrZero(source.summary?.goCount ?? source.go_count ?? source.goCount ?? fallbackSource.summary?.goCount),
      manualCount: numberOrZero(source.summary?.manualCount ?? source.manual_review_required ?? source.manualReviewRequired ?? fallbackSource.summary?.manualCount),
      alerts: arrayOrEmpty(source.summary?.alerts ?? fallbackSource.summary?.alerts).map(stringOrEmpty),
      pendingReviews: numberOrZero(source.pending_reviews ?? source.pendingReviews ?? fallbackSource.summary?.pendingReviews),
      approvedToday: numberOrZero(source.approved_today ?? source.approvedToday ?? fallbackSource.summary?.approvedToday),
      manualReviewRequired: numberOrZero(source.manual_review_required ?? source.manualReviewRequired ?? fallbackSource.summary?.manualReviewRequired),
      blockedReviews: numberOrZero(source.blocked_reviews ?? source.blockedReviews ?? fallbackSource.summary?.blockedReviews),
      overdueReviews: numberOrZero(source.overdue_reviews ?? source.overdueReviews ?? fallbackSource.summary?.overdueReviews),
      operatorCapacity: numberOrZero(source.operator_capacity ?? source.operatorCapacity ?? fallbackSource.summary?.operatorCapacity ?? 1000),
      operatorCapacityUsed: numberOrZero(source.operator_capacity_used ?? source.operatorCapacityUsed ?? fallbackSource.summary?.operatorCapacityUsed),
      operatorCapacityRemaining: numberOrZero(source.operator_capacity_remaining ?? source.operatorCapacityRemaining ?? fallbackSource.summary?.operatorCapacityRemaining),
      queueLagMinutes: numberOrZero(source.queue_lag_minutes ?? source.queueLagMinutes ?? fallbackSource.summary?.queueLagMinutes),
    },
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
  };
}

export function normalizeHarvestHealth(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const sources = Array.isArray(source.sources) && source.sources.length ? source.sources : arrayOrEmpty(fallbackSource.sources);
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    sources: sources.map((item, index) => ({
      id: stringOrEmpty(item?.id || `source-${index}`),
      name: stringOrEmpty(item?.name),
      tier: stringOrEmpty(item?.tier || "Tier 3"),
      active: Boolean(item?.active),
      eligible: numberOrZero(item?.eligible),
      total: numberOrZero(item?.total),
      status: stringOrEmpty(item?.status || "advisory"),
      failureCount: numberOrZero(item?.failureCount ?? item?.failure_count),
      parserFailureRate: numberOrZero(item?.parserFailureRate ?? item?.parser_failure_rate),
      evidenceStale: Boolean(item?.evidenceStale ?? item?.evidence_stale),
      lastUpdatedAt: stringOrEmpty(item?.lastUpdatedAt ?? item?.last_updated_at),
    })),
    totalSources: numberOrZero(source.total_sources ?? source.totalSources ?? fallbackSource.totalSources ?? sources.length),
    activeSources: numberOrZero(source.active_sources ?? source.activeSources ?? fallbackSource.activeSources),
    healthySources: numberOrZero(source.healthy_sources ?? source.healthySources ?? fallbackSource.healthySources),
    degradedSources: numberOrZero(source.degraded_sources ?? source.degradedSources ?? fallbackSource.degradedSources),
    failingSources: numberOrZero(source.failing_sources ?? source.failingSources ?? fallbackSource.failingSources),
    disabledSources: numberOrZero(source.disabled_sources ?? source.disabledSources ?? fallbackSource.disabledSources),
    parserFailureRate: numberOrZero(source.parser_failure_rate ?? source.parserFailureRate ?? fallbackSource.parserFailureRate),
    averageResponseTimeMs: numberOrZero(source.average_response_time_ms ?? source.averageResponseTimeMs ?? fallbackSource.averageResponseTimeMs),
    recentSourceFailures: arrayOrEmpty(source.recent_source_failures ?? source.recentSourceFailures ?? fallbackSource.recentSourceFailures).map((item) => ({
      sourceId: stringOrEmpty(item?.source_id ?? item?.sourceId),
      name: stringOrEmpty(item?.name),
      status: stringOrEmpty(item?.status || "unknown"),
      failureCount: numberOrZero(item?.failure_count ?? item?.failureCount),
      consecutiveFailures: numberOrZero(item?.consecutive_failures ?? item?.consecutiveFailures),
      parserFailureRate: numberOrZero(item?.parser_failure_rate ?? item?.parserFailureRate),
    })),
    summary: {
      totalSources: numberOrZero(source.total_sources ?? source.totalSources ?? fallbackSource.totalSources ?? sources.length),
      activeSources: numberOrZero(source.active_sources ?? source.activeSources ?? fallbackSource.activeSources),
      healthySources: numberOrZero(source.healthy_sources ?? source.healthySources ?? fallbackSource.healthySources),
      degradedSources: numberOrZero(source.degraded_sources ?? source.degradedSources ?? fallbackSource.degradedSources),
      failingSources: numberOrZero(source.failing_sources ?? source.failingSources ?? fallbackSource.failingSources),
      disabledSources: numberOrZero(source.disabled_sources ?? source.disabledSources ?? fallbackSource.disabledSources),
      parserFailureRate: numberOrZero(source.parser_failure_rate ?? source.parserFailureRate ?? fallbackSource.parserFailureRate),
      averageResponseTimeMs: numberOrZero(source.average_response_time_ms ?? source.averageResponseTimeMs ?? fallbackSource.averageResponseTimeMs),
      recentSourceFailures: arrayOrEmpty(source.recent_source_failures ?? source.recentSourceFailures ?? fallbackSource.recentSourceFailures),
    },
  };
}

export function normalizeQualificationSummary(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    goCount: numberOrZero(source.go_count ?? source.goCount ?? fallbackSource.goCount),
    manualReviewCount: numberOrZero(source.manual_review_count ?? source.manualReviewCount ?? fallbackSource.manualReviewCount),
    rejectCount: numberOrZero(source.reject_count ?? source.rejectCount ?? fallbackSource.rejectCount),
    lowConfidenceCount: numberOrZero(source.low_confidence_count ?? source.lowConfidenceCount ?? fallbackSource.lowConfidenceCount),
    topRejectionReasons: arrayOrEmpty(source.top_rejection_reasons ?? source.topRejectionReasons ?? fallbackSource.topRejectionReasons).map(stringOrEmpty),
    topManualReviewTriggers: arrayOrEmpty(source.top_manual_review_triggers ?? source.topManualReviewTriggers ?? fallbackSource.topManualReviewTriggers).map(stringOrEmpty),
    avgQualificationScore: numberOrZero(source.avg_qualification_score ?? source.avgQualificationScore ?? fallbackSource.avgQualificationScore),
    avgRiskScore: numberOrZero(source.avg_risk_score ?? source.avgRiskScore ?? fallbackSource.avgRiskScore),
    manualGovernanceOnly: Boolean(source.manualGovernanceOnly ?? fallbackSource.manualGovernanceOnly ?? true),
    reviewReadyRequired: Boolean(source.reviewReadyRequired ?? fallbackSource.reviewReadyRequired ?? true),
    proofCaptureRequired: Boolean(source.proofCaptureRequired ?? fallbackSource.proofCaptureRequired ?? true),
  };
}

export function normalizeOperationalHealth(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    sourceFailures: numberOrZero(source.source_failures ?? source.sourceFailures ?? fallbackSource.sourceFailures),
    parserFailures: numberOrZero(source.parser_failures ?? source.parserFailures ?? fallbackSource.parserFailures),
    queueLag: numberOrZero(source.queue_lag ?? source.queueLag ?? fallbackSource.queueLag),
    operatorCapacity: numberOrZero(source.operator_capacity ?? source.operatorCapacity ?? fallbackSource.operatorCapacity ?? 1000),
    rfqAging: numberOrZero(source.rfq_aging ?? source.rfqAging ?? fallbackSource.rfqAging),
    staleEvidence: numberOrZero(source.stale_evidence ?? source.staleEvidence ?? fallbackSource.staleEvidence),
    workflowFailures: numberOrZero(source.workflow_failures ?? source.workflowFailures ?? fallbackSource.workflowFailures),
    persistenceFailures: numberOrZero(source.persistence_failures ?? source.persistenceFailures ?? fallbackSource.persistenceFailures),
    auditFailures: numberOrZero(source.audit_failures ?? source.auditFailures ?? fallbackSource.auditFailures),
    governanceComplianceScore: numberOrZero(source.governance_compliance_score ?? source.governanceComplianceScore ?? fallbackSource.governanceComplianceScore),
    manualGovernanceIntegrityScore: numberOrZero(source.manual_governance_integrity_score ?? source.manualGovernanceIntegrityScore ?? fallbackSource.manualGovernanceIntegrityScore),
  };
}
