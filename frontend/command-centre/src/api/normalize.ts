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

function normalizeState(value, fallback = "unknown") {
  return stringOrEmpty(value || fallback);
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
    tierBreakdown: source.tier_breakdown ?? source.tierBreakdown ?? fallbackSource.tierBreakdown ?? {},
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
      tierBreakdown: source.tier_breakdown ?? source.tierBreakdown ?? fallbackSource.tierBreakdown ?? {},
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

function normalizeExecutiveTrendRows(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row, index) => ({
    label: stringOrEmpty(row?.label || row?.week || row?.month || `bucket-${index}`),
    count: numberOrZero(row?.count ?? row?.rfqs),
    total: numberOrZero(row?.total ?? row?.value),
    go: numberOrZero(row?.go),
    manualReview: numberOrZero(row?.manual_review ?? row?.manualReview),
    reject: numberOrZero(row?.reject),
  }));
}

function normalizeGenericArray(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row) => (isObject(row) ? row : { value: row }));
}

function normalizeExecutiveSummary(source, fallback = {}) {
  const fallbackSummary = fallback.executiveSummary || fallback.summary || fallback.commandMetrics || {};
  return {
    rfqsHarvested: numberOrZero(source.rfqs_harvested ?? source.rfqsHarvested ?? fallbackSummary.rfqsHarvested ?? fallbackSummary.totalHarvested),
    rfqsQualified: numberOrZero(source.rfqs_qualified ?? source.rfqsQualified ?? fallbackSummary.rfqsQualified ?? fallbackSummary.eligibleRfqs),
    rfqsReviewed: numberOrZero(source.rfqs_reviewed ?? source.rfqsReviewed ?? fallbackSummary.rfqsReviewed),
    goTrend: numberOrZero(source.go_trend ?? source.goTrend ?? fallbackSummary.goTrend),
    manualReviewTrend: numberOrZero(source.manual_review_trend ?? source.manualReviewTrend ?? fallbackSummary.manualReviewTrend),
    rejectTrend: numberOrZero(source.reject_trend ?? source.rejectTrend ?? fallbackSummary.rejectTrend),
    estimatedProfitability: numberOrZero(source.estimated_profitability ?? source.estimatedProfitability ?? fallbackSummary.estimatedProfitability ?? fallbackSummary.estimatedValue),
    operatorThroughput: numberOrZero(source.operator_throughput ?? source.operatorThroughput ?? fallbackSummary.operatorThroughput),
    queuePressure: numberOrZero(source.queue_pressure ?? source.queuePressure ?? fallbackSummary.queuePressure),
    governanceIncidents: numberOrZero(source.governance_incidents ?? source.governanceIncidents ?? fallbackSummary.governanceIncidents),
    sourceReliability: numberOrZero(source.source_reliability ?? source.sourceReliability ?? fallbackSummary.sourceReliability),
    slaHealth: stringOrEmpty(source.sla_health ?? source.slaHealth ?? fallbackSummary.slaHealth ?? "healthy"),
    qualifiedRate: numberOrZero(source.qualified_rate ?? source.qualifiedRate ?? fallbackSummary.qualifiedRate),
    manualGovernanceIntegrityScore: numberOrZero(source.manual_governance_integrity_score ?? source.manualGovernanceIntegrityScore ?? fallbackSummary.manualGovernanceIntegrityScore),
    operationalReliabilityScore: numberOrZero(source.operational_reliability_score ?? source.operationalReliabilityScore ?? fallbackSummary.operationalReliabilityScore),
    qualityScore: numberOrZero(source.quality_score ?? source.qualityScore ?? fallbackSummary.qualityScore),
  };
}

export function normalizeExecutiveAnalytics(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    executiveSummary: normalizeExecutiveSummary(source.executive_summary ?? source.executiveSummary ?? source.summary ?? {}, fallbackSource),
    weeklyTrend: normalizeExecutiveTrendRows(source.weekly_trend ?? source.weeklyTrend, fallbackSource.weeklyTrend),
    monthlyTrend: normalizeExecutiveTrendRows(source.monthly_trend ?? source.monthlyTrend, fallbackSource.monthlyTrend),
    rollingAverages: {
      weeklyTotal: arrayOrEmpty(source.rolling_averages?.weekly_total ?? source.rollingAverages?.weeklyTotal ?? fallbackSource.rollingAverages?.weeklyTotal).map(numberOrZero),
      monthlyTotal: arrayOrEmpty(source.rolling_averages?.monthly_total ?? source.rollingAverages?.monthlyTotal ?? fallbackSource.rollingAverages?.monthlyTotal).map(numberOrZero),
    },
    profitability: source.profitability ?? source.profitability_summary ?? fallbackSource.profitability ?? {},
    rfqConversion: source.rfq_conversion ?? source.rfqConversion ?? fallbackSource.rfqConversion ?? {},
    sourceROI: source.source_roi ?? source.sourceROI ?? fallbackSource.sourceROI ?? {},
    operatorTrends: source.operator_trends ?? source.operatorTrends ?? fallbackSource.operatorTrends ?? {},
    governanceTrends: source.governance_trends ?? source.governanceTrends ?? fallbackSource.governanceTrends ?? {},
    workloadForecast: source.workload_forecast ?? source.workloadForecast ?? fallbackSource.workloadForecast ?? {},
    opportunityForecast: source.opportunity_forecast ?? source.opportunityForecast ?? fallbackSource.opportunityForecast ?? {},
    revenueProjection: source.revenue_projection ?? source.revenueProjection ?? fallbackSource.revenueProjection ?? {},
    historicalTrends: source.historical_trends ?? source.historicalTrends ?? fallbackSource.historicalTrends ?? {},
    productivity: source.productivity ?? fallbackSource.productivity ?? {},
    sourceReliability: source.source_reliability ?? source.sourceReliability ?? fallbackSource.sourceReliability ?? {},
    sla: source.sla ?? fallbackSource.sla ?? {},
    runtimeMetrics: source.runtime_metrics ?? source.runtimeMetrics ?? fallbackSource.runtimeMetrics ?? {},
    workflowSummary: source.workflow_summary ?? source.workflowSummary ?? fallbackSource.workflowSummary ?? {},
    pilotReadiness: source.pilot_readiness ?? source.pilotReadiness ?? fallbackSource.pilotReadiness ?? {},
    tenderSuccessAnalytics: source.tender_success_analytics ?? source.tenderSuccessAnalytics ?? fallbackSource.tenderSuccessAnalytics ?? {},
    observabilitySummary: source.observability_summary ?? source.observabilitySummary ?? fallbackSource.observabilitySummary ?? {},
    strategicHighlights: arrayOrEmpty(source.strategic_highlights ?? source.strategicHighlights ?? fallbackSource.strategicHighlights).map(stringOrEmpty),
  };
}

export function normalizeProfitabilityAnalytics(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const summary = source.summary ?? fallbackSource.summary ?? {};
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    summary: {
      estimatedTotalProfit: numberOrZero(summary.estimated_total_profit ?? summary.estimatedTotalProfit),
      averageEstimatedProfit: numberOrZero(summary.average_estimated_profit ?? summary.averageEstimatedProfit),
      averageMargin: numberOrZero(summary.average_margin ?? summary.averageMargin),
      highValueRfqCount: numberOrZero(summary.high_value_rfq_count ?? summary.highValueRfqCount),
      lowConfidenceProfitabilityCount: numberOrZero(summary.low_confidence_profitability_count ?? summary.lowConfidenceProfitabilityCount),
      stalePricingImpactCount: numberOrZero(summary.stale_pricing_impact_count ?? summary.stalePricingImpactCount),
      supplierEvidenceImpactAverage: numberOrZero(summary.supplier_evidence_impact_average ?? summary.supplierEvidenceImpactAverage),
    },
    estimatedRfqProfitability: normalizeGenericArray(source.estimated_rfq_profitability ?? source.estimatedRfqProfitability, fallbackSource.estimatedRfqProfitability).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `rfq-${index}`),
      title: stringOrEmpty(row?.title),
      estimatedProfit: numberOrZero(row?.estimated_profit ?? row?.estimatedProfit),
      estimatedMargin: numberOrZero(row?.estimated_margin ?? row?.estimatedMargin),
      province: stringOrEmpty(row?.province),
      source: stringOrEmpty(row?.source),
    })),
    estimatedMarginDistribution: source.estimated_margin_distribution ?? source.estimatedMarginDistribution ?? fallbackSource.estimatedMarginDistribution ?? {},
    highValueRfqs: normalizeGenericArray(source.high_value_rfqs ?? source.highValueRfqs, fallbackSource.highValueRfqs).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `high-${index}`),
      title: stringOrEmpty(row?.title),
      estimatedProfit: numberOrZero(row?.estimated_profit ?? row?.estimatedProfit),
      estimatedMargin: numberOrZero(row?.estimated_margin ?? row?.estimatedMargin),
      province: stringOrEmpty(row?.province),
      source: stringOrEmpty(row?.source),
    })),
    lowConfidenceProfitability: normalizeGenericArray(source.low_confidence_profitability ?? source.lowConfidenceProfitability, fallbackSource.lowConfidenceProfitability).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `low-${index}`),
      title: stringOrEmpty(row?.title),
      pricingConfidence: numberOrZero(row?.pricing_confidence ?? row?.pricingConfidence),
    })),
    stalePricingImpact: normalizeGenericArray(source.stale_pricing_impact ?? source.stalePricingImpact, fallbackSource.stalePricingImpact).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `stale-${index}`),
      title: stringOrEmpty(row?.title),
    })),
    supplierEvidenceImpact: normalizeGenericArray(source.supplier_evidence_impact ?? source.supplierEvidenceImpact, fallbackSource.supplierEvidenceImpact).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `evidence-${index}`),
      supplierEvidenceScore: numberOrZero(row?.supplier_evidence_score ?? row?.supplierEvidenceScore),
    })),
    profitabilityBySource: normalizeGenericArray(source.profitability_by_source ?? source.profitabilityBySource, fallbackSource.profitabilityBySource).map((row, index) => ({
      source: stringOrEmpty(row?.source ?? row?.name ?? `source-${index}`),
      estimatedProfit: numberOrZero(row?.estimated_profit ?? row?.estimatedProfit),
      count: numberOrZero(row?.count),
    })),
    profitabilityByProvince: normalizeGenericArray(source.profitability_by_province ?? source.profitabilityByProvince, fallbackSource.profitabilityByProvince).map((row, index) => ({
      province: stringOrEmpty(row?.province ?? `province-${index}`),
      estimatedProfit: numberOrZero(row?.estimated_profit ?? row?.estimatedProfit),
      count: numberOrZero(row?.count),
    })),
  };
}

export function normalizeForecastingAnalytics(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const workload = isObject(source.workload_forecast) ? source.workload_forecast : fallbackSource.workloadForecast || {};
  const opportunity = isObject(source.opportunity_forecast) ? source.opportunity_forecast : fallbackSource.opportunityForecast || {};
  const revenue = isObject(source.revenue_projection) ? source.revenue_projection : fallbackSource.revenueProjection || {};
  const mergedSummary = {
    queueGrowth: numberOrZero(workload.summary?.queue_growth ?? workload.summary?.queueGrowth ?? fallbackSource.summary?.queueGrowth),
    operatorWorkload: numberOrZero(workload.summary?.operator_workload ?? workload.summary?.operatorWorkload ?? fallbackSource.summary?.operatorWorkload),
    rfqThroughput: numberOrZero(workload.summary?.rfq_throughput ?? workload.summary?.rfqThroughput ?? fallbackSource.summary?.rfqThroughput),
    sourceGrowth: numberOrZero(workload.summary?.source_growth ?? workload.summary?.sourceGrowth ?? fallbackSource.summary?.sourceGrowth),
    estimatedReviewDemand: numberOrZero(workload.summary?.estimated_review_demand ?? workload.summary?.estimatedReviewDemand ?? fallbackSource.summary?.estimatedReviewDemand),
    rfqGrowth: numberOrZero(opportunity.summary?.rfq_growth ?? opportunity.summary?.rfqGrowth ?? fallbackSource.summary?.rfqGrowth),
    reviewDemand: numberOrZero(opportunity.summary?.review_demand ?? opportunity.summary?.reviewDemand ?? fallbackSource.summary?.reviewDemand),
    opportunityValueProjection: numberOrZero(revenue.summary?.projected_rfq_opportunity_value ?? revenue.summary?.projectedRfqOpportunityValue ?? fallbackSource.summary?.opportunityValueProjection),
  };
  return {
    status: stringOrEmpty(source.status || workload.status || opportunity.status || revenue.status || fallbackSource.status || "runtime_fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || workload.generated_at || opportunity.generated_at || revenue.generated_at || fallbackSource.generatedAt || fallbackSource.lastRefreshedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || workload.data_source || opportunity.data_source || revenue.data_source || fallbackSource.dataSource || "runtime_fallback"),
    summary: mergedSummary,
    forecast: source.forecast ?? {
      workload: workload.forecast || {},
      opportunity: opportunity.forecast || {},
      revenue: revenue.summary || {},
    },
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? true),
    estimated: Boolean(source.estimated ?? true),
    nonFinancialAdvice: Boolean(source.non_financial_advice ?? source.nonFinancialAdvice ?? true),
    heuristic: Boolean(source.heuristic ?? true),
  };
}

function normalizeOperatorActionRecord(record, index = 0) {
  return {
    actionId: stringOrEmpty(record?.action_id ?? record?.actionId ?? `action-${index}`),
    action: stringOrEmpty(record?.action),
    operatorId: stringOrEmpty(record?.operator_id ?? record?.operatorId),
    tenderId: stringOrEmpty(record?.tender_id ?? record?.tenderId),
    targetType: stringOrEmpty(record?.target_type ?? record?.targetType ?? "rfq"),
    note: stringOrEmpty(record?.note),
    status: stringOrEmpty(record?.status ?? "queued_for_manual_followup"),
    reversible: Boolean(record?.reversible ?? true),
    reviewable: Boolean(record?.reviewable ?? true),
    auditEventId: stringOrEmpty(record?.audit_event_id ?? record?.auditEventId),
    createdAt: stringOrEmpty(record?.created_at ?? record?.createdAt),
    updatedAt: stringOrEmpty(record?.updated_at ?? record?.updatedAt),
    details: isObject(record?.details) ? record.details : {},
  };
}

export function normalizeOperatorActions(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const actions = Array.isArray(source.actions) && source.actions.length ? source.actions : arrayOrEmpty(fallbackSource.actions);
  const normalized = actions.map((item, index) => normalizeOperatorActionRecord(item, index));
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    actions: normalized,
    total: numberOrZero(source.total ?? fallbackSource.total ?? normalized.length),
  };
}

function normalizeOperatorAssignmentRecord(record, index = 0) {
  return {
    assignmentId: stringOrEmpty(record?.assignment_id ?? record?.assignmentId ?? `assignment-${index}`),
    operatorId: stringOrEmpty(record?.operator_id ?? record?.operatorId),
    tenderId: stringOrEmpty(record?.tender_id ?? record?.tenderId),
    status: stringOrEmpty(record?.status ?? "assigned"),
    priority: numberOrZero(record?.priority),
    assignedAt: stringOrEmpty(record?.assigned_at ?? record?.assignedAt),
    dueAt: stringOrEmpty(record?.due_at ?? record?.dueAt),
    workload: numberOrZero(record?.workload),
    recommendation: stringOrEmpty(record?.recommendation ?? "manual"),
    source: stringOrEmpty(record?.source ?? "runtime"),
    details: isObject(record?.details) ? record.details : {},
  };
}

export function normalizeOperatorAssignments(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const assignments = Array.isArray(source.assignments) && source.assignments.length ? source.assignments : arrayOrEmpty(fallbackSource.assignments);
  const recommendations = Array.isArray(source.recommendations) && source.recommendations.length ? source.recommendations : arrayOrEmpty(fallbackSource.recommendations);
  const normalizedAssignments = assignments.map((item, index) => normalizeOperatorAssignmentRecord(item, index));
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    assignments: normalizedAssignments,
    recommendations: recommendations.map((item, index) => ({
      tenderId: stringOrEmpty(item?.tender_id ?? item?.tenderId ?? `recommendation-${index}`),
      title: stringOrEmpty(item?.title ?? item?.name ?? "Unknown RFQ"),
      recommendation: stringOrEmpty(item?.recommendation ?? "manual"),
      priority: numberOrZero(item?.priority),
      workflowStage: stringOrEmpty(item?.workflow_stage ?? item?.workflowStage ?? "unknown"),
      owner: stringOrEmpty(item?.owner ?? ""),
      reason: stringOrEmpty(item?.reason ?? ""),
      dueAt: stringOrEmpty(item?.due_at ?? item?.dueAt),
    })),
    summary: {
      totalAssignments: numberOrZero(source.summary?.total_assignments ?? fallbackSource.summary?.totalAssignments ?? normalizedAssignments.length),
      activeAssignments: numberOrZero(source.summary?.active_assignments ?? fallbackSource.summary?.activeAssignments ?? normalizedAssignments.length),
      operators: numberOrZero(source.summary?.operators ?? fallbackSource.summary?.operators ?? 10),
      capacity: numberOrZero(source.summary?.capacity ?? fallbackSource.summary?.capacity ?? 1000),
    },
    capacity: {
      teamSize: numberOrZero(source.capacity?.team_size ?? source.capacity?.teamSize ?? fallbackSource.capacity?.teamSize ?? 10),
      perOperatorDailyCapacity: numberOrZero(source.capacity?.per_operator_daily_capacity ?? source.capacity?.perOperatorDailyCapacity ?? fallbackSource.capacity?.perOperatorDailyCapacity ?? 100),
      totalDailyCapacity: numberOrZero(source.capacity?.total_daily_capacity ?? source.capacity?.totalDailyCapacity ?? fallbackSource.capacity?.totalDailyCapacity ?? 1000),
      assignedToday: numberOrZero(source.capacity?.assigned_today ?? source.capacity?.assignedToday ?? fallbackSource.capacity?.assignedToday ?? normalizedAssignments.length),
      remainingCapacity: numberOrZero(source.capacity?.remaining_capacity ?? source.capacity?.remainingCapacity ?? fallbackSource.capacity?.remainingCapacity ?? Math.max(0, 1000 - normalizedAssignments.length)),
      overloaded: Boolean(source.capacity?.overloaded ?? fallbackSource.capacity?.overloaded ?? normalizedAssignments.length >= 1000),
      recommendedLoad: numberOrZero(source.capacity?.recommended_load ?? source.capacity?.recommendedLoad ?? fallbackSource.capacity?.recommendedLoad ?? recommendations.length),
      generatedAt: stringOrEmpty(
        source.capacity?.generated_at ??
          source.capacity?.generatedAt ??
          fallbackSource.capacity?.generatedAt ??
          source.generated_at ??
          source.generatedAt ??
          fallbackSource.generatedAt,
      ),
      dataSource: stringOrEmpty(
        source.capacity?.data_source ??
          source.capacity?.dataSource ??
          fallbackSource.capacity?.dataSource ??
          source.data_source ??
          source.dataSource ??
          fallbackSource.dataSource ??
          "runtime_fallback",
      ),
    },
  };
}

function normalizeOperatorTimelineEvent(record, index = 0) {
  return {
    eventId: stringOrEmpty(record?.event_id ?? record?.eventId ?? `event-${index}`),
    eventType: stringOrEmpty(record?.event_type ?? record?.eventType),
    operatorId: stringOrEmpty(record?.operator_id ?? record?.operatorId),
    tenderId: stringOrEmpty(record?.tender_id ?? record?.tenderId),
    title: stringOrEmpty(record?.title ?? "Operator event"),
    severity: stringOrEmpty(record?.severity ?? "info"),
    reversible: Boolean(record?.reversible ?? true),
    reviewable: Boolean(record?.reviewable ?? true),
    createdAt: stringOrEmpty(record?.created_at ?? record?.createdAt),
    details: isObject(record?.details) ? record.details : {},
  };
}

export function normalizeOperatorTimeline(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const events = Array.isArray(source.events) && source.events.length ? source.events : arrayOrEmpty(fallbackSource.events);
  const normalized = events.map((item, index) => normalizeOperatorTimelineEvent(item, index));
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    events: normalized,
    total: numberOrZero(source.total ?? fallbackSource.total ?? normalized.length),
  };
}

function normalizeOperatorNotificationRecord(record, index = 0) {
  return {
    notificationId: stringOrEmpty(record?.notification_id ?? record?.notificationId ?? `notification-${index}`),
    type: stringOrEmpty(record?.type ?? "info"),
    severity: stringOrEmpty(record?.severity ?? "info"),
    title: stringOrEmpty(record?.title ?? ""),
    message: stringOrEmpty(record?.message ?? ""),
    tenderId: stringOrEmpty(record?.tender_id ?? record?.tenderId),
    operatorId: stringOrEmpty(record?.operator_id ?? record?.operatorId),
    acknowledged: Boolean(record?.acknowledged ?? false),
    createdAt: stringOrEmpty(record?.created_at ?? record?.createdAt),
    details: isObject(record?.details) ? record.details : {},
  };
}

export function normalizeOperatorNotifications(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const notifications = Array.isArray(source.notifications) && source.notifications.length ? source.notifications : arrayOrEmpty(fallbackSource.notifications);
  const normalized = notifications.map((item, index) => normalizeOperatorNotificationRecord(item, index));
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    notifications: normalized,
  };
}

export function normalizeOperatorCapacity(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const teamSize = numberOrZero(source.team_size ?? source.teamSize ?? fallbackSource.teamSize ?? 10);
  const perOperatorDailyCapacity = numberOrZero(source.per_operator_daily_capacity ?? source.perOperatorDailyCapacity ?? fallbackSource.perOperatorDailyCapacity ?? 100);
  const totalDailyCapacity = numberOrZero(source.total_daily_capacity ?? source.totalDailyCapacity ?? fallbackSource.totalDailyCapacity ?? 1000);
  const assignedToday = numberOrZero(source.assigned_today ?? source.assignedToday ?? fallbackSource.assignedToday);
  const remainingCapacity = numberOrZero(source.remaining_capacity ?? source.remainingCapacity ?? fallbackSource.remainingCapacity ?? Math.max(0, totalDailyCapacity - assignedToday));
  const recommendedLoad = numberOrZero(source.recommended_load ?? source.recommendedLoad ?? fallbackSource.recommendedLoad);
  return {
    status: stringOrEmpty(source.status || fallbackSource.status || "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: stringOrEmpty(source.data_source || source.dataSource || fallbackSource.dataSource || "runtime_fallback"),
    teamSize,
    perOperatorDailyCapacity,
    totalDailyCapacity,
    assignedToday,
    remainingCapacity,
    overloaded: Boolean(source.overloaded ?? fallbackSource.overloaded ?? assignedToday >= totalDailyCapacity),
    recommendedLoad,
  };
}

export function normalizeRFQWorkflowResponse(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const rows = arrayOrEmpty(source.rows ?? source.data ?? fallbackSource.rows).map((row, index) => ({
    tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `rfq-${index + 1}`),
    title: stringOrEmpty(row?.title),
    buyer: stringOrEmpty(row?.buyer),
    province: stringOrEmpty(row?.province),
    qualificationState: normalizeState(row?.qualification_state ?? row?.qualificationState, "MANUAL_REVIEW"),
    estimatedProfit: numberOrZero(row?.estimated_profit ?? row?.estimatedProfit),
    estimatedMargin: numberOrZero(row?.estimated_margin ?? row?.estimatedMargin),
    riskLevel: normalizeState(row?.risk_level ?? row?.riskLevel, "medium"),
    workflowStage: normalizeState(row?.workflow_stage ?? row?.workflowStage, "unknown"),
    reviewStatus: normalizeState(row?.review_status ?? row?.reviewStatus, "manual_review_required"),
    pricingConfidence: numberOrZero(row?.pricing_confidence ?? row?.pricingConfidence),
    sourceTier: stringOrEmpty(row?.source_tier ?? row?.sourceTier),
    submissionMethod: normalizeState(row?.submission_method ?? row?.submissionMethod, "unknown"),
    dataSource: normalizeState(row?.data_source ?? row?.dataSource ?? source.data_source ?? source.dataSource ?? fallbackSource.dataSource, "runtime_fallback"),
    lastUpdated: stringOrEmpty(row?.last_updated ?? row?.lastUpdated),
    qualification: row?.qualification ?? {},
    pricingEvidence: row?.pricing_evidence ?? row?.pricingEvidence ?? {},
    pricingTraceability: row?.pricing_traceability ?? row?.pricingTraceability ?? {},
  }));

  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || fallbackSource.lastUpdatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    summary: {
      total: numberOrZero(source.summary?.total ?? fallbackSource.summary?.total ?? rows.length),
      go: numberOrZero(source.summary?.go ?? fallbackSource.summary?.go),
      manualReview: numberOrZero(source.summary?.manual_review ?? source.summary?.manualReview ?? fallbackSource.summary?.manualReview),
      reject: numberOrZero(source.summary?.reject ?? fallbackSource.summary?.reject),
      dataSource: normalizeState(source.summary?.data_source ?? source.summary?.dataSource ?? fallbackSource.summary?.dataSource ?? source.data_source, "runtime_fallback"),
    },
    rows,
  };
}

export function normalizeRFQWorkflowDetail(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const summary = source.summary || fallbackSource.summary || {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    tenderId: stringOrEmpty(source.tender_id || source.tenderId || fallbackSource.tenderId),
    summary: {
      title: stringOrEmpty(summary.title),
      buyer: stringOrEmpty(summary.buyer),
      province: stringOrEmpty(summary.province),
      workflowStage: stringOrEmpty(summary.workflow_stage || summary.workflowStage),
      reviewStatus: stringOrEmpty(summary.review_status || summary.reviewStatus),
    },
    qualificationSummary: source.qualification_summary || source.qualificationSummary || fallbackSource.qualificationSummary || {},
    riskSummary: source.risk_summary || source.riskSummary || fallbackSource.riskSummary || {},
    pricingEvidence: source.pricing_evidence || source.pricingEvidence || fallbackSource.pricingEvidence || {},
    pricingValidation: source.pricing_validation || source.pricingValidation || fallbackSource.pricingValidation || {},
    pricingTraceability: source.pricing_traceability || source.pricingTraceability || fallbackSource.pricingTraceability || {},
    governanceSummary: source.governance_summary || source.governanceSummary || fallbackSource.governanceSummary || {},
    workflowHistory: arrayOrEmpty(source.workflow_history || source.workflowHistory || fallbackSource.workflowHistory).map((entry) => ({
      tenderId: stringOrEmpty(entry?.tender_id || entry?.tenderId),
      stage: stringOrEmpty(entry?.stage),
      updatedAt: stringOrEmpty(entry?.updated_at || entry?.updatedAt),
      details: entry?.details || {},
    })),
    operationalWarnings: arrayOrEmpty(source.operational_warnings || source.operationalWarnings || fallbackSource.operationalWarnings).map(stringOrEmpty),
    recommendationReasons: arrayOrEmpty(source.recommendation_reasons || source.recommendationReasons || fallbackSource.recommendationReasons).map(stringOrEmpty),
    manualReviewTriggers: arrayOrEmpty(source.manual_review_triggers || source.manualReviewTriggers || fallbackSource.manualReviewTriggers).map(stringOrEmpty),
    disqualificationTriggers: arrayOrEmpty(source.disqualification_triggers || source.disqualificationTriggers || fallbackSource.disqualificationTriggers).map(stringOrEmpty),
    sourceHealth: source.source_health || source.sourceHealth || fallbackSource.sourceHealth || {},
    dataSourceLabel: stringOrEmpty(source.data_source_label || source.dataSourceLabel || fallbackSource.dataSourceLabel || source.data_source || source.dataSource),
  };
}

export function normalizeQualificationInsights(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const summary = source.summary || fallbackSource.summary || {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    summary,
    provinceHeat: source.province_heat || source.provinceHeat || fallbackSource.provinceHeat || {},
    lowConfidenceRfqs: arrayOrEmpty(source.low_confidence_rfqs || source.lowConfidenceRfqs || fallbackSource.lowConfidenceRfqs),
    riskDistribution: source.risk_distribution || source.riskDistribution || fallbackSource.riskDistribution || {},
    qualificationScoreAverage: numberOrZero(source.qualification_score_average ?? source.qualificationScoreAverage ?? fallbackSource.qualificationScoreAverage),
    riskScoreAverage: numberOrZero(source.risk_score_average ?? source.riskScoreAverage ?? fallbackSource.riskScoreAverage),
    topRejectionReasons: arrayOrEmpty(source.top_rejection_reasons ?? source.topRejectionReasons ?? fallbackSource.topRejectionReasons).map(stringOrEmpty),
    topManualReviewTriggers: arrayOrEmpty(source.top_manual_review_triggers ?? source.topManualReviewTriggers ?? fallbackSource.topManualReviewTriggers).map(stringOrEmpty),
    goCount: numberOrZero(source.go_count ?? source.goCount ?? fallbackSource.goCount),
    manualReviewCount: numberOrZero(source.manual_review_count ?? source.manualReviewCount ?? fallbackSource.manualReviewCount),
    rejectCount: numberOrZero(source.reject_count ?? source.rejectCount ?? fallbackSource.rejectCount),
  };
}

export function normalizePricingEvidence(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    summary: {
      supplier_quote_completeness_average: numberOrZero(source.summary?.supplier_quote_completeness_average ?? fallbackSource.summary?.supplier_quote_completeness_average),
      pricing_defensibility_average: numberOrZero(source.summary?.pricing_defensibility_average ?? fallbackSource.summary?.pricing_defensibility_average),
      pricing_confidence_average: numberOrZero(source.summary?.pricing_confidence_average ?? fallbackSource.summary?.pricing_confidence_average),
      stale_quote_count: numberOrZero(source.summary?.stale_quote_count ?? fallbackSource.summary?.stale_quote_count),
      vat_mismatch_count: numberOrZero(source.summary?.vat_mismatch_count ?? fallbackSource.summary?.vat_mismatch_count),
      subtotal_mismatch_count: numberOrZero(source.summary?.subtotal_mismatch_count ?? fallbackSource.summary?.subtotal_mismatch_count),
      delivery_inconsistency_count: numberOrZero(source.summary?.delivery_inconsistency_count ?? fallbackSource.summary?.delivery_inconsistency_count),
    },
    pricingEvidenceRows: arrayOrEmpty(source.pricing_evidence_rows || source.pricingEvidenceRows || fallbackSource.pricingEvidenceRows).map((row, index) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `pricing-${index + 1}`),
      title: stringOrEmpty(row?.title),
      supplierEvidenceScore: numberOrZero(row?.supplier_evidence_score ?? row?.supplierEvidenceScore),
      pricingDefensibilityScore: numberOrZero(row?.pricing_defensibility_score ?? row?.pricingDefensibilityScore),
      pricingConfidence: numberOrZero(row?.pricing_confidence ?? row?.pricingConfidence),
      quoteAgeDays: numberOrZero(row?.quote_age_days ?? row?.quoteAgeDays),
      riskLevel: stringOrEmpty(row?.risk_level ?? row?.riskLevel),
      operatorOverrideNotes: stringOrEmpty(row?.operator_override_notes ?? row?.operatorOverrideNotes),
      traceabilityChain: arrayOrEmpty(row?.traceability_chain ?? row?.traceabilityChain),
    })),
    pricingAnomalies: arrayOrEmpty(source.pricing_anomalies ?? source.pricingAnomalies ?? fallbackSource.pricingAnomalies).map((row) => ({
      name: stringOrEmpty(row?.name),
      count: numberOrZero(row?.count),
    })),
  };
}

export function normalizeSourceHealthDetails(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    rows: arrayOrEmpty(source.rows ?? fallbackSource.rows).map((row, index) => ({
      sourceId: stringOrEmpty(row?.source_id ?? row?.sourceId ?? `source-${index}`),
      name: stringOrEmpty(row?.name),
      sourceTier: stringOrEmpty(row?.source_tier ?? row?.sourceTier),
      parserType: stringOrEmpty(row?.parser_type ?? row?.parserType),
      status: stringOrEmpty(row?.status),
      lastSuccess: stringOrEmpty(row?.last_success ?? row?.lastSuccess),
      lastFailure: stringOrEmpty(row?.last_failure ?? row?.lastFailure),
      failureCount: numberOrZero(row?.failure_count ?? row?.failureCount),
      averageResponseTimeMs: numberOrZero(row?.average_response_time_ms ?? row?.averageResponseTimeMs),
      parserFailureRate: numberOrZero(row?.parser_failure_rate ?? row?.parserFailureRate),
      healthState: stringOrEmpty(row?.health_state ?? row?.healthState),
    })),
    tierBreakdown: source.tier_breakdown || source.tierBreakdown || fallbackSource.tierBreakdown || {},
    summary: {
      totalSources: numberOrZero(source.summary?.total_sources ?? source.summary?.totalSources ?? fallbackSource.summary?.totalSources),
      healthySources: numberOrZero(source.summary?.healthy_sources ?? source.summary?.healthySources ?? fallbackSource.summary?.healthySources),
      degradedSources: numberOrZero(source.summary?.degraded_sources ?? source.summary?.degradedSources ?? fallbackSource.summary?.degradedSources),
      failingSources: numberOrZero(source.summary?.failing_sources ?? source.summary?.failingSources ?? fallbackSource.summary?.failingSources),
      disabledSources: numberOrZero(source.summary?.disabled_sources ?? source.summary?.disabledSources ?? fallbackSource.summary?.disabledSources),
    },
  };
}

export function normalizeRuntimeMetrics(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    metrics: {
      rfqsHarvestedPerHour: numberOrZero(source.rfqs_harvested_per_hour ?? source.metrics?.rfqsHarvestedPerHour ?? fallbackSource.metrics?.rfqsHarvestedPerHour),
      reviewThroughput: numberOrZero(source.review_throughput ?? source.metrics?.reviewThroughput ?? fallbackSource.metrics?.reviewThroughput),
      queueLag: numberOrZero(source.queue_lag ?? source.metrics?.queueLag ?? fallbackSource.metrics?.queueLag),
      operatorUtilization: numberOrZero(source.operator_utilization ?? source.metrics?.operatorUtilization ?? fallbackSource.metrics?.operatorUtilization),
      parserFailureRate: numberOrZero(source.parser_failure_rate ?? source.metrics?.parserFailureRate ?? fallbackSource.metrics?.parserFailureRate),
      sourceAvailability: numberOrZero(source.source_availability ?? source.metrics?.sourceAvailability ?? fallbackSource.metrics?.sourceAvailability),
      telemetryFreshnessMinutes: numberOrZero(source.telemetry_freshness_minutes ?? source.metrics?.telemetryFreshnessMinutes ?? fallbackSource.metrics?.telemetryFreshnessMinutes),
      workflowFailures: numberOrZero(source.workflow_failures ?? source.metrics?.workflowFailures ?? fallbackSource.metrics?.workflowFailures),
      persistenceFailures: numberOrZero(source.persistence_failures ?? source.metrics?.persistenceFailures ?? fallbackSource.metrics?.persistenceFailures),
      authFailures: numberOrZero(source.auth_failures ?? source.metrics?.authFailures ?? fallbackSource.metrics?.authFailures),
      rateLimitEvents: numberOrZero(source.rate_limit_events ?? source.metrics?.rateLimitEvents ?? fallbackSource.metrics?.rateLimitEvents),
      apiLatencyMs: numberOrZero(source.api_latency_ms ?? source.metrics?.apiLatencyMs ?? fallbackSource.metrics?.apiLatencyMs),
    },
    systemHealth: source.system_health ?? fallbackSource.systemHealth ?? {},
    operatorCapacity: source.operator_capacity ?? fallbackSource.operatorCapacity ?? {},
    queueSummary: source.queue_summary ?? fallbackSource.queueSummary ?? {},
    sourceSummary: source.source_summary ?? fallbackSource.sourceSummary ?? {},
    workflowSummary: source.workflow_summary ?? fallbackSource.workflowSummary ?? {},
    persistence: source.persistence ?? fallbackSource.persistence ?? {},
  };
}

export function normalizeRuntimeAlerts(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    alerts: arrayOrEmpty(source.alerts ?? fallbackSource.alerts).map((item, index) => ({
      alertId: stringOrEmpty(item?.alert_id ?? item?.alertId ?? `alert-${index}`),
      type: stringOrEmpty(item?.type),
      severity: stringOrEmpty(item?.severity),
      title: stringOrEmpty(item?.title),
      message: stringOrEmpty(item?.message),
      createdAt: stringOrEmpty(item?.created_at ?? item?.createdAt),
      acknowledged: Boolean(item?.acknowledged),
      details: isObject(item?.details) ? item.details : {},
    })),
    total: numberOrZero(source.total ?? fallbackSource.total),
    alertSeverities: arrayOrEmpty(source.alert_severities ?? source.alertSeverities ?? fallbackSource.alertSeverities).map(stringOrEmpty),
  };
}

export function normalizeIncidentTracker(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const incidents = arrayOrEmpty(source.incidents ?? fallbackSource.incidents).map((item, index) => ({
    incidentId: stringOrEmpty(item?.incident_id ?? item?.incidentId ?? `incident-${index}`),
    incidentType: stringOrEmpty(item?.incident_type ?? item?.incidentType),
    title: stringOrEmpty(item?.title),
    severity: stringOrEmpty(item?.severity),
    status: stringOrEmpty(item?.status),
    operatorId: stringOrEmpty(item?.operator_id ?? item?.operatorId),
    createdAt: stringOrEmpty(item?.created_at ?? item?.createdAt),
    updatedAt: stringOrEmpty(item?.updated_at ?? item?.updatedAt),
    acknowledgedAt: stringOrEmpty(item?.acknowledged_at ?? item?.acknowledgedAt),
    acknowledgedBy: stringOrEmpty(item?.acknowledged_by ?? item?.acknowledgedBy),
    details: isObject(item?.details) ? item.details : {},
  }));
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    totalIncidents: numberOrZero(source.total_incidents ?? fallbackSource.totalIncidents ?? incidents.length),
    severityCounts: source.severity_counts ?? source.severityCounts ?? fallbackSource.severityCounts ?? {},
    statusCounts: source.status_counts ?? source.statusCounts ?? fallbackSource.statusCounts ?? {},
    activeCriticalIncidents: numberOrZero(source.active_critical_incidents ?? source.activeCriticalIncidents ?? fallbackSource.activeCriticalIncidents),
    incidents,
  };
}

export function normalizeBackupValidation(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    backupCount: numberOrZero(source.backup_count ?? fallbackSource.backupCount),
    backupDir: stringOrEmpty(source.backup_dir ?? fallbackSource.backupDir),
    latestBackup: stringOrEmpty(source.latest_backup ?? fallbackSource.latestBackup),
    latestBackupVerified: Boolean(source.latest_backup_verified ?? fallbackSource.latestBackupVerified),
    latestBackupAgeDays: numberOrZero(source.latest_backup_age_days ?? fallbackSource.latestBackupAgeDays),
    auditPersistenceOk: Boolean(source.audit_persistence_ok ?? fallbackSource.auditPersistenceOk),
    restoreSimulation: isObject(source.restore_simulation) ? source.restore_simulation : fallbackSource.restoreSimulation || {},
  };
}

function normalizeSlaMetric(item, index = 0) {
  return {
    name: stringOrEmpty(item?.name ?? `metric-${index}`),
    value: numberOrZero(item?.value),
    state: normalizeState(item?.state, "healthy"),
  };
}

function normalizeRuntimeAnomaly(item, index = 0) {
  return {
    anomalyId: stringOrEmpty(item?.anomaly_id ?? item?.anomalyId ?? `anomaly-${index}`),
    type: stringOrEmpty(item?.type),
    severity: normalizeState(item?.severity, "warning"),
    message: stringOrEmpty(item?.message),
    affectedSystems: arrayOrEmpty(item?.affected_systems ?? item?.affectedSystems).map(stringOrEmpty),
    evidence: isObject(item?.evidence) ? item.evidence : {},
    createdAt: stringOrEmpty(item?.created_at ?? item?.createdAt),
    advisoryOnly: Boolean(item?.advisory_only ?? item?.advisoryOnly ?? true),
  };
}

export function normalizeSlaMonitoring(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const slaMetrics = arrayOrEmpty(source.sla_metrics ?? source.slaMetrics ?? fallbackSource.slaMetrics).map(normalizeSlaMetric);
  const breachedMetrics = arrayOrEmpty(source.breached_metrics ?? source.breachedMetrics ?? fallbackSource.breachedMetrics).map(normalizeSlaMetric);
  const warningMetrics = arrayOrEmpty(source.warning_metrics ?? source.warningMetrics ?? fallbackSource.warningMetrics).map(normalizeSlaMetric);
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    slaMetrics,
    breachedMetrics,
    warningMetrics,
    summary: {
      healthy: numberOrZero(source.summary?.healthy ?? fallbackSource.summary?.healthy ?? slaMetrics.filter((item) => item.state === "healthy").length),
      degraded: numberOrZero(source.summary?.degraded ?? fallbackSource.summary?.degraded ?? warningMetrics.length),
      failing: numberOrZero(source.summary?.failing ?? fallbackSource.summary?.failing ?? breachedMetrics.length),
    },
  };
}

export function normalizeRuntimeAnomalies(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const anomalies = arrayOrEmpty(source.anomalies ?? fallbackSource.anomalies).map(normalizeRuntimeAnomaly);
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    anomalies,
    anomalyCount: numberOrZero(source.anomaly_count ?? source.anomalyCount ?? fallbackSource.anomalyCount ?? anomalies.length),
    severityCounts: source.severity_counts ?? source.severityCounts ?? fallbackSource.severityCounts ?? {},
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? fallbackSource.advisoryOnly ?? true),
  };
}

export function normalizeAlertRouting(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    alerts: arrayOrEmpty(source.alerts ?? fallbackSource.alerts).map((item, index) => ({
      alertId: stringOrEmpty(item?.alert_id ?? item?.alertId ?? `alert-${index}`),
      severity: normalizeState(item?.severity, "info"),
      category: stringOrEmpty(item?.category ?? item?.type),
      targets: arrayOrEmpty(item?.targets).map(stringOrEmpty),
      advisoryOnly: Boolean(item?.advisory_only ?? item?.advisoryOnly ?? true),
    })),
    routeCount: numberOrZero(source.route_count ?? source.routeCount ?? fallbackSource.routeCount),
    categoryCounts: source.category_counts ?? source.categoryCounts ?? fallbackSource.categoryCounts ?? {},
    targetCounts: source.target_counts ?? source.targetCounts ?? fallbackSource.targetCounts ?? {},
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? fallbackSource.advisoryOnly ?? true),
  };
}

export function normalizeLogAggregation(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    totalLogs: numberOrZero(source.total_logs ?? source.totalLogs ?? fallbackSource.totalLogs),
    logSources: source.log_sources ?? source.logSources ?? fallbackSource.logSources ?? {},
    categoryCounts: source.category_counts ?? source.categoryCounts ?? fallbackSource.categoryCounts ?? {},
    severityDistribution: source.severity_distribution ?? source.severityDistribution ?? fallbackSource.severityDistribution ?? {},
    redactedSamples: arrayOrEmpty(source.redacted_samples ?? source.redactedSamples ?? fallbackSource.redactedSamples).map(stringOrEmpty),
  };
}

export function normalizeUptimeMonitor(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    apiUptimePercentage: numberOrZero(source.api_uptime_percentage ?? source.apiUptimePercentage ?? fallbackSource.apiUptimePercentage),
    observedWindowMinutes: numberOrZero(source.observed_window_minutes ?? source.observedWindowMinutes ?? fallbackSource.observedWindowMinutes),
    systemHealth: source.system_health ?? source.systemHealth ?? fallbackSource.systemHealth ?? {},
    runtimeMetrics: source.runtime_metrics ?? source.runtimeMetrics ?? fallbackSource.runtimeMetrics ?? {},
  };
}

export function normalizeRuntimePerformance(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    apiLatencyMs: numberOrZero(source.api_latency_ms ?? source.apiLatencyMs ?? fallbackSource.apiLatencyMs),
    queueResponseTimeMs: numberOrZero(source.queue_response_time_ms ?? source.queueResponseTimeMs ?? fallbackSource.queueResponseTimeMs),
    dbResponseHealth: normalizeState(source.db_response_health ?? source.dbResponseHealth ?? fallbackSource.dbResponseHealth, "unknown"),
    frontendBuildFreshnessMinutes: numberOrZero(source.frontend_build_freshness_minutes ?? source.frontendBuildFreshnessMinutes ?? fallbackSource.frontendBuildFreshnessMinutes),
    deploymentHealth: normalizeState(source.deployment_health ?? source.deploymentHealth ?? fallbackSource.deploymentHealth, "degraded"),
    telemetryFreshnessMinutes: numberOrZero(source.telemetry_freshness_minutes ?? source.telemetryFreshnessMinutes ?? fallbackSource.telemetryFreshnessMinutes),
  };
}

export function normalizeObservabilitySnapshot(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const prometheus = isObject(source.prometheus) ? source.prometheus : fallbackSource.prometheus || {};
  const grafana = isObject(source.grafana) ? source.grafana : fallbackSource.grafana || {};
  const sentry = isObject(source.sentry) ? source.sentry : fallbackSource.sentry || {};
  const sla = normalizeSlaMonitoring(source.sla ?? {}, fallbackSource.sla ?? {});
  const anomalies = normalizeRuntimeAnomalies(source.anomalies ?? {}, fallbackSource.anomalies ?? {});
  const alerts = normalizeAlertRouting(source.alerts ?? {}, fallbackSource.alerts ?? {});
  const logs = normalizeLogAggregation(source.logs ?? {}, fallbackSource.logs ?? {});
  const uptime = normalizeUptimeMonitor(source.uptime ?? {}, fallbackSource.uptime ?? {});
  const performance = normalizeRuntimePerformance(source.performance ?? {}, fallbackSource.performance ?? {});
  const prometheusText = stringOrEmpty(prometheus.text ?? fallbackSource.prometheus?.text);
  const prometheusMetricCount = numberOrZero(
    prometheus.metrics_count ?? prometheus.metricsCount ?? fallbackSource.prometheus?.metricsCount ?? prometheusText.split("\n").filter((line) => line.startsWith("lmcp_")).length,
  );

  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    prometheus: {
      status: normalizeState(prometheus.status || fallbackSource.prometheus?.status, "runtime_fallback"),
      generatedAt: stringOrEmpty(prometheus.generated_at || prometheus.generatedAt || fallbackSource.prometheus?.generatedAt || fallbackSource.generatedAt),
      dataSource: normalizeState(prometheus.data_source || prometheus.dataSource || fallbackSource.prometheus?.dataSource, "runtime_fallback"),
      metricsCount: prometheusMetricCount,
      metrics: prometheus.metrics ?? fallbackSource.prometheus?.metrics ?? {},
      text: prometheusText,
    },
    grafana: {
      status: normalizeState(grafana.status || fallbackSource.grafana?.status, "runtime_fallback"),
      generatedAt: stringOrEmpty(grafana.generated_at || grafana.generatedAt || fallbackSource.grafana?.generatedAt || fallbackSource.generatedAt),
      dataSource: normalizeState(grafana.data_source || grafana.dataSource || fallbackSource.grafana?.dataSource, "runtime_fallback"),
      dashboards: arrayOrEmpty(grafana.dashboards ?? fallbackSource.grafana?.dashboards),
      count: numberOrZero(grafana.count ?? fallbackSource.grafana?.count),
    },
    sentry: {
      status: normalizeState(sentry.status || fallbackSource.sentry?.status, "fallback"),
      generatedAt: stringOrEmpty(sentry.generated_at || sentry.generatedAt || fallbackSource.sentry?.generatedAt || fallbackSource.generatedAt),
      dataSource: normalizeState(sentry.data_source || sentry.dataSource || fallbackSource.sentry?.dataSource, "fallback"),
      sentry: sentry.sentry ?? fallbackSource.sentry?.sentry ?? {},
    },
    sla,
    anomalies,
    alerts,
    logs,
    uptime,
    performance,
    summary: {
      prometheusMetricsCount: numberOrZero(prometheus.metrics_count ?? prometheus.metricsCount ?? fallbackSource.prometheus?.metricsCount),
      grafanaDashboards: numberOrZero(grafana.count ?? fallbackSource.grafana?.count),
      runtimeAlerts: numberOrZero(alerts.routeCount ?? fallbackSource.alerts?.routeCount),
      anomalyCount: numberOrZero(anomalies.anomalyCount ?? fallbackSource.anomalies?.anomalyCount),
      logCount: numberOrZero(logs.totalLogs ?? fallbackSource.logs?.totalLogs),
      uptimePercent: numberOrZero(uptime.apiUptimePercentage ?? fallbackSource.uptime?.apiUptimePercentage),
      slaStatus: sla.status,
      anomalyStatus: anomalies.status,
      performanceStatus: performance.status,
    },
  };
}

function normalizeOperatorWorkloadOperator(row, index = 0) {
  return {
    operatorId: stringOrEmpty(row?.operator_id ?? row?.operatorId ?? `operator-${index + 1}`),
    assigned: numberOrZero(row?.assigned),
    overdue: numberOrZero(row?.overdue),
    utilization: numberOrZero(row?.utilization),
    timelineEvents: numberOrZero(row?.timeline_events ?? row?.timelineEvents),
    specialization: stringOrEmpty(row?.specialization, "general"),
    workloadScore: numberOrZero(row?.workload_score ?? row?.workloadScore),
    averageDueAgeHours: numberOrZero(row?.average_due_age_hours ?? row?.averageDueAgeHours),
    priorityAverage: numberOrZero(row?.priority_average ?? row?.priorityAverage),
  };
}

export function normalizeOperatorWorkload(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const operators = Array.isArray(source.operators) && source.operators.length ? source.operators : arrayOrEmpty(fallbackSource.operators);
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    teamSize: numberOrZero(source.team_size ?? source.teamSize ?? fallbackSource.teamSize ?? 10),
    totalDailyCapacity: numberOrZero(source.total_daily_capacity ?? source.totalDailyCapacity ?? fallbackSource.totalDailyCapacity ?? 1000),
    assignedToday: numberOrZero(source.assigned_today ?? source.assignedToday ?? fallbackSource.assignedToday),
    remainingCapacity: numberOrZero(source.remaining_capacity ?? source.remainingCapacity ?? fallbackSource.remainingCapacity),
    averageUtilization: numberOrZero(source.average_utilization ?? source.averageUtilization ?? fallbackSource.averageUtilization),
    averageWorkloadScore: numberOrZero(source.average_workload_score ?? source.averageWorkloadScore ?? fallbackSource.averageWorkloadScore),
    overloadWarnings: arrayOrEmpty(source.overload_warnings ?? source.overloadWarnings ?? fallbackSource.overloadWarnings).map(stringOrEmpty),
    underutilizationWarnings: arrayOrEmpty(source.underutilization_warnings ?? source.underutilizationWarnings ?? fallbackSource.underutilizationWarnings).map(stringOrEmpty),
    operators: operators.map((row, index) => normalizeOperatorWorkloadOperator(row, index)),
  };
}

function normalizeReviewQueueOptimizationItem(row, index = 0) {
  return {
    tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId ?? `item-${index + 1}`),
    title: stringOrEmpty(row?.title, "Unknown RFQ"),
    buyer: stringOrEmpty(row?.buyer, "Unknown buyer"),
    province: stringOrEmpty(row?.province, "Unknown"),
    closingDate: stringOrEmpty(row?.closing_date ?? row?.closingDate),
    workflowStage: stringOrEmpty(row?.workflow_stage ?? row?.workflowStage, "review_ready"),
    reviewStatus: stringOrEmpty(row?.review_status ?? row?.reviewStatus, "pending"),
    pricingConfidence: numberOrZero(row?.pricing_confidence ?? row?.pricingConfidence),
    queueAgeMinutes: numberOrZero(row?.queue_age_minutes ?? row?.queueAgeMinutes),
    priorityScore: numberOrZero(row?.priority_score ?? row?.priorityScore),
    priorityGroup: stringOrEmpty(row?.priority_group ?? row?.priorityGroup, "low"),
    priorityReason: stringOrEmpty(row?.priority_reason ?? row?.priorityReason),
    riskLevel: stringOrEmpty(row?.risk_level ?? row?.riskLevel, "medium"),
    staleEvidence: Boolean(row?.stale_evidence ?? row?.staleEvidence),
    reviewReadiness: stringOrEmpty(row?.review_readiness ?? row?.reviewReadiness, "manual"),
    governanceBlocked: Boolean(row?.governance_blocked ?? row?.governanceBlocked),
    submissionMethod: stringOrEmpty(row?.submission_method ?? row?.submissionMethod, "unknown"),
    sourceTier: stringOrEmpty(row?.source_tier ?? row?.sourceTier, "Tier 4"),
    dataSource: stringOrEmpty(row?.data_source ?? row?.dataSource, "runtime"),
  };
}

export function normalizeReviewQueueOptimization(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const items = Array.isArray(source.optimized_queue) && source.optimized_queue.length ? source.optimized_queue : arrayOrEmpty(fallbackSource.optimizedQueue);
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    optimizedQueue: items.map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    priorityGroups: source.priority_groups ?? source.priorityGroups ?? fallbackSource.priorityGroups ?? {},
    overdueReviews: arrayOrEmpty(source.overdue_reviews ?? source.overdueReviews ?? fallbackSource.overdueReviews).map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    staleRfqs: arrayOrEmpty(source.stale_rfqs ?? source.staleRfqs ?? fallbackSource.staleRfqs).map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    overloadedQueue: Boolean(source.overloaded_queue ?? source.overloadedQueue ?? fallbackSource.overloadedQueue),
    summary: {
      total: numberOrZero(source.summary?.total ?? fallbackSource.summary?.total ?? items.length),
      urgent: numberOrZero(source.summary?.urgent ?? fallbackSource.summary?.urgent),
      high: numberOrZero(source.summary?.high ?? fallbackSource.summary?.high),
      medium: numberOrZero(source.summary?.medium ?? fallbackSource.summary?.medium),
      low: numberOrZero(source.summary?.low ?? fallbackSource.summary?.low),
      averagePriorityScore: numberOrZero(source.summary?.average_priority_score ?? source.summary?.averagePriorityScore ?? fallbackSource.summary?.averagePriorityScore),
      averageQueueAgeMinutes: numberOrZero(source.summary?.average_queue_age_minutes ?? source.summary?.averageQueueAgeMinutes ?? fallbackSource.summary?.averageQueueAgeMinutes),
    },
  };
}

export function normalizeReviewEfficiency(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    rfqsReviewedPerHour: numberOrZero(source.rfqs_reviewed_per_hour ?? source.rfqsReviewedPerHour ?? fallbackSource.rfqsReviewedPerHour),
    reviewCompletionTimeMinutes: numberOrZero(source.review_completion_time_minutes ?? source.reviewCompletionTimeMinutes ?? fallbackSource.reviewCompletionTimeMinutes),
    evidenceHandlingTimeMinutes: numberOrZero(source.evidence_handling_time_minutes ?? source.evidenceHandlingTimeMinutes ?? fallbackSource.evidenceHandlingTimeMinutes),
    escalationFrequency: numberOrZero(source.escalation_frequency ?? source.escalationFrequency ?? fallbackSource.escalationFrequency),
    reassignmentFrequency: numberOrZero(source.reassignment_frequency ?? source.reassignmentFrequency ?? fallbackSource.reassignmentFrequency),
    queueAgingTrends: source.queue_aging_trends ?? source.queueAgingTrends ?? fallbackSource.queueAgingTrends ?? {},
    operatorThroughputTrends: source.operator_throughput_trends ?? source.operatorThroughputTrends ?? fallbackSource.operatorThroughputTrends ?? {},
    timelineGapMinutes: numberOrZero(source.timeline_gap_minutes ?? source.timelineGapMinutes ?? fallbackSource.timelineGapMinutes),
    throughputBottlenecks: arrayOrEmpty(source.throughput_bottlenecks ?? source.throughputBottlenecks ?? fallbackSource.throughputBottlenecks),
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? fallbackSource.advisoryOnly ?? true),
  };
}

export function normalizeFocusSessions(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const sessions = Array.isArray(source.sessions) && source.sessions.length ? source.sessions : arrayOrEmpty(fallbackSource.sessions);
  return {
    status: normalizeState(source.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    sessions: sessions.map((row) => ({
      operatorId: stringOrEmpty(row?.operator_id ?? row?.operatorId, "unassigned"),
      focusedMinutes: numberOrZero(row?.focused_minutes ?? row?.focusedMinutes),
      reviewThroughput: numberOrZero(row?.review_throughput ?? row?.reviewThroughput),
      interruptionCount: numberOrZero(row?.interruption_count ?? row?.interruptionCount),
      completionBursts: numberOrZero(row?.completion_bursts ?? row?.completionBursts),
      sessionStart: stringOrEmpty(row?.session_start ?? row?.sessionStart),
      sessionEnd: stringOrEmpty(row?.session_end ?? row?.sessionEnd),
    })),
    summary: source.summary ?? fallbackSource.summary ?? {},
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? true),
  };
}

export function normalizeQueueHeatmap(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    heatmap: arrayOrEmpty(source.heatmap ?? fallbackSource.heatmap).map((row) => ({
      axis: stringOrEmpty(row?.axis),
      label: stringOrEmpty(row?.label),
      value: numberOrZero(row?.value),
    })),
    operatorDistribution: source.operator_distribution ?? source.operatorDistribution ?? fallbackSource.operatorDistribution ?? {},
    sourceDistribution: source.source_distribution ?? source.sourceDistribution ?? fallbackSource.sourceDistribution ?? {},
    escalationDensity: source.escalation_density ?? source.escalationDensity ?? fallbackSource.escalationDensity ?? {},
    provinceDensity: source.province_density ?? source.provinceDensity ?? fallbackSource.provinceDensity ?? {},
  };
}

export function normalizeReviewPriorities(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const groupKeys = ["urgent", "high", "medium", "low"];
  const priorityGroups = {};
  for (const key of groupKeys) {
    const rows = Array.isArray(source.priority_groups?.[key]) ? source.priority_groups[key] : arrayOrEmpty(fallbackSource.priorityGroups?.[key]);
    priorityGroups[key] = rows.map((row, index) => normalizeReviewQueueOptimizationItem(row, index));
  }
  return {
    status: normalizeState(source.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    priorityScore: numberOrZero(source.priority_score ?? source.priorityScore ?? fallbackSource.priorityScore),
    priorityGroups,
    escalationRecommendations: arrayOrEmpty(source.escalation_recommendations ?? source.escalationRecommendations ?? fallbackSource.escalationRecommendations),
    reviewUrgency: stringOrEmpty(source.review_urgency ?? source.reviewUrgency, "normal"),
    overloadedQueue: Boolean(source.overloaded_queue ?? source.overloadedQueue ?? fallbackSource.overloadedQueue),
  };
}

export function normalizeEvidenceAcceleration(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    missingEvidence: arrayOrEmpty(source.missing_evidence ?? source.missingEvidence ?? fallbackSource.missingEvidence).map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    staleEvidence: arrayOrEmpty(source.stale_evidence ?? source.staleEvidence ?? fallbackSource.staleEvidence).map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    supplierQuoteCompleteness: arrayOrEmpty(source.supplier_quote_completeness ?? source.supplierQuoteCompleteness ?? fallbackSource.supplierQuoteCompleteness).map((row) => ({
      tenderId: stringOrEmpty(row?.tender_id ?? row?.tenderId),
      title: stringOrEmpty(row?.title),
      pricingConfidence: numberOrZero(row?.pricing_confidence ?? row?.pricingConfidence),
      queueAgeMinutes: numberOrZero(row?.queue_age_minutes ?? row?.queueAgeMinutes),
    })),
    pricingMismatchSummary: arrayOrEmpty(source.pricing_mismatch_summary ?? source.pricingMismatchSummary ?? fallbackSource.pricingMismatchSummary).map((row, index) => normalizeReviewQueueOptimizationItem(row, index)),
    groupedWarnings: source.grouped_warnings ?? source.groupedWarnings ?? fallbackSource.groupedWarnings ?? {},
    summary: source.summary ?? fallbackSource.summary ?? {},
  };
}

export function normalizeOperatorShortcuts(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  return {
    status: normalizeState(source.status || fallbackSource.status, "ok"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    shortcuts: arrayOrEmpty(source.shortcuts ?? fallbackSource.shortcuts).map((row) => ({
      label: stringOrEmpty(row?.label),
      key: stringOrEmpty(row?.key),
      action: stringOrEmpty(row?.action),
    })),
    quickActions: arrayOrEmpty(source.quick_actions ?? source.quickActions ?? fallbackSource.quickActions).map(stringOrEmpty),
    filterPresets: arrayOrEmpty(source.filter_presets ?? source.filterPresets ?? fallbackSource.filterPresets).map(stringOrEmpty),
    advisoryOnly: Boolean(source.advisory_only ?? source.advisoryOnly ?? fallbackSource.advisoryOnly ?? true),
  };
}

export function normalizeProductivitySnapshot(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const workload = normalizeOperatorWorkload(source.workload ?? {}, fallbackSource.workload ?? {});
  const queueOptimization = normalizeReviewQueueOptimization(source.queueOptimization ?? source.queue_optimization ?? {}, fallbackSource.queueOptimization ?? {});
  const reviewEfficiency = normalizeReviewEfficiency(source.reviewEfficiency ?? source.review_efficiency ?? {}, fallbackSource.reviewEfficiency ?? {});
  const focusSessions = normalizeFocusSessions(source.focusSessions ?? source.focus_sessions ?? {}, fallbackSource.focusSessions ?? {});
  const queueHeatmap = normalizeQueueHeatmap(source.queueHeatmap ?? source.queue_heatmap ?? {}, fallbackSource.queueHeatmap ?? {});
  const reviewPriorities = normalizeReviewPriorities(source.reviewPriorities ?? source.review_priorities ?? {}, fallbackSource.reviewPriorities ?? {});
  const evidenceAcceleration = normalizeEvidenceAcceleration(source.evidenceAcceleration ?? source.evidence_acceleration ?? {}, fallbackSource.evidenceAcceleration ?? {});
  const shortcuts = normalizeOperatorShortcuts(source.shortcuts ?? {}, fallbackSource.shortcuts ?? {});
  return {
    status: normalizeState(source.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || workload.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource || workload.dataSource, "runtime_fallback"),
    workload,
    queueOptimization,
    reviewEfficiency,
    focusSessions,
    queueHeatmap,
    reviewPriorities,
    evidenceAcceleration,
    shortcuts,
  };
}

function normalizeWrappedPayload(payload, key) {
  const source = isObject(payload) ? payload : {};
  const wrapped = isObject(source[key]) ? source[key] : source;
  return { source, wrapped };
}

function normalizeStabilizationTrendRows(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row, index) => ({
    label: stringOrEmpty(row?.label || row?.name || row?.kind || `trend-${index}`),
    value: numberOrZero(row?.value),
    healthy: numberOrZero(row?.healthy),
    degraded: numberOrZero(row?.degraded),
    failing: numberOrZero(row?.failing),
  }));
}

function normalizeStabilizationCheckRows(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row, index) => ({
    label: stringOrEmpty(row?.label || row?.name || `check-${index}`),
    status: stringOrEmpty(row?.status || row?.state, "unknown"),
    passed: Boolean(row?.passed ?? row?.ok ?? row?.compliant),
    detail: stringOrEmpty(row?.detail || row?.message || row?.description),
    severity: stringOrEmpty(row?.severity || "info"),
  }));
}

function normalizeStabilizationOperatorRows(rows, fallback = []) {
  const sourceRows = Array.isArray(rows) && rows.length ? rows : arrayOrEmpty(fallback);
  return sourceRows.map((row, index) => ({
    operatorId: stringOrEmpty(row?.operator_id ?? row?.operatorId ?? `operator-${index + 1}`),
    workloadScore: numberOrZero(row?.workload_score ?? row?.workloadScore),
    fatigueScore: numberOrZero(row?.fatigue_score ?? row?.fatigueScore),
    warning: stringOrEmpty(row?.warning),
    recommendation: stringOrEmpty(row?.recommendation),
    overdueReviews: numberOrZero(row?.overdue_reviews ?? row?.overdueReviews),
    repeatedEscalations: numberOrZero(row?.repeated_escalations ?? row?.repeatedEscalations),
    prolongedQueueExposure: numberOrZero(row?.prolonged_queue_exposure ?? row?.prolongedQueueExposure),
    focusSessionExhaustion: numberOrZero(row?.focus_session_exhaustion ?? row?.focusSessionExhaustion),
  }));
}

export function normalizeStabilizationRuntime(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "runtime_stability");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.runtime_stability) ? fallbackSource.runtime_stability : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    stabilityScore: numberOrZero(wrapped.stability_score ?? wrapped.stabilityScore ?? fallbackWrapped.stabilityScore),
    degradationTrends: normalizeStabilizationTrendRows(wrapped.degradation_trends ?? wrapped.degradationTrends, fallbackWrapped.degradationTrends),
    operationalWarnings: arrayOrEmpty(wrapped.operational_warnings ?? wrapped.operationalWarnings ?? fallbackWrapped.operationalWarnings).map(stringOrEmpty),
    snapshotHealth: wrapped.snapshot_health ?? wrapped.snapshotHealth ?? fallbackWrapped.snapshotHealth ?? {},
    queueLagMinutes: numberOrZero(wrapped.queue_lag_minutes ?? wrapped.queueLagMinutes ?? fallbackWrapped.queueLagMinutes),
    telemetryFreshnessMinutes: numberOrZero(wrapped.telemetry_freshness_minutes ?? wrapped.telemetryFreshnessMinutes ?? fallbackWrapped.telemetryFreshnessMinutes),
    workerStaleCount: numberOrZero(wrapped.worker_stale_count ?? wrapped.workerStaleCount ?? fallbackWrapped.workerStaleCount),
    sourceFailureCount: numberOrZero(wrapped.source_failure_count ?? wrapped.sourceFailureCount ?? fallbackWrapped.sourceFailureCount),
    alertCount: numberOrZero(wrapped.alert_count ?? wrapped.alertCount ?? fallbackWrapped.alertCount),
    anomalyCount: numberOrZero(wrapped.anomaly_count ?? wrapped.anomalyCount ?? fallbackWrapped.anomalyCount),
    windowSize: numberOrZero(wrapped.window_size ?? wrapped.windowSize ?? fallbackWrapped.windowSize),
    signals: wrapped.signals ?? fallbackWrapped.signals ?? {},
  };
}

export function normalizeStabilizationFallbackHealth(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "fallback_health");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.fallback_health) ? fallbackSource.fallback_health : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    fallbackHealthSummary: wrapped.fallback_health_summary ?? wrapped.fallbackHealthSummary ?? fallbackWrapped.fallbackHealthSummary ?? {},
    fallbackActivations: numberOrZero(wrapped.fallback_activations ?? wrapped.fallbackActivations ?? fallbackWrapped.fallbackActivations),
    staleFallbacks: numberOrZero(wrapped.stale_fallbacks ?? wrapped.staleFallbacks ?? fallbackWrapped.staleFallbacks),
    runtimeRecoverySuccess: Boolean(wrapped.runtime_recovery_success ?? wrapped.runtimeRecoverySuccess ?? fallbackWrapped.runtimeRecoverySuccess),
    recoverySuccessRate: numberOrZero(wrapped.recovery_success_rate ?? wrapped.recoverySuccessRate ?? fallbackWrapped.recoverySuccessRate),
    warnings: arrayOrEmpty(wrapped.warnings ?? fallbackWrapped.warnings).map(stringOrEmpty),
    blockers: arrayOrEmpty(wrapped.blockers ?? fallbackWrapped.blockers).map(stringOrEmpty),
    advisoryOnly: Boolean(wrapped.advisory_only ?? wrapped.advisoryOnly ?? fallbackWrapped.advisoryOnly ?? true),
  };
}

export function normalizeStabilizationTelemetryNoise(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "telemetry_noise");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.telemetry_noise) ? fallbackSource.telemetry_noise : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    alerts: arrayOrEmpty(wrapped.alerts ?? fallbackWrapped.alerts).map((row) => ({
      alertId: stringOrEmpty(row?.alert_id ?? row?.alertId),
      type: stringOrEmpty(row?.type),
      severity: stringOrEmpty(row?.severity || "info"),
      title: stringOrEmpty(row?.title),
      message: stringOrEmpty(row?.message),
      createdAt: stringOrEmpty(row?.created_at ?? row?.createdAt),
      acknowledged: Boolean(row?.acknowledged),
      details: row?.details ?? {},
    })),
    alertGroups: arrayOrEmpty(wrapped.alert_groups ?? wrapped.alertGroups ?? fallbackWrapped.alertGroups).map((row) => ({
      label: stringOrEmpty(row?.label),
      count: numberOrZero(row?.count),
      severity: stringOrEmpty(row?.severity || "info"),
    })),
    severityCounts: wrapped.severity_counts ?? wrapped.severityCounts ?? fallbackWrapped.severityCounts ?? {},
    suppressedCount: numberOrZero(wrapped.suppressed_count ?? wrapped.suppressedCount ?? fallbackWrapped.suppressedCount),
    retainedCount: numberOrZero(wrapped.retained_count ?? wrapped.retainedCount ?? fallbackWrapped.retainedCount),
    criticalCount: numberOrZero(wrapped.critical_count ?? wrapped.criticalCount ?? fallbackWrapped.criticalCount),
    noiseScore: numberOrZero(wrapped.noise_score ?? wrapped.noiseScore ?? fallbackWrapped.noiseScore),
    advisoryOnly: Boolean(wrapped.advisory_only ?? wrapped.advisoryOnly ?? fallbackWrapped.advisoryOnly ?? true),
  };
}

export function normalizeStabilizationGovernanceConsistency(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "governance_consistency");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.governance_consistency) ? fallbackSource.governance_consistency : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    consistencyScore: numberOrZero(wrapped.consistency_score ?? wrapped.consistencyScore ?? fallbackWrapped.consistencyScore),
    checks: normalizeStabilizationCheckRows(wrapped.checks ?? fallbackWrapped.checks),
    inconsistencies: arrayOrEmpty(wrapped.inconsistencies ?? fallbackWrapped.inconsistencies).map(stringOrEmpty),
    warnings: arrayOrEmpty(wrapped.warnings ?? fallbackWrapped.warnings).map(stringOrEmpty),
    blockers: arrayOrEmpty(wrapped.blockers ?? fallbackWrapped.blockers).map(stringOrEmpty),
    auditAttributionMissing: Boolean(wrapped.audit_attribution_missing ?? wrapped.auditAttributionMissing ?? fallbackWrapped.auditAttributionMissing),
    roleDistribution: wrapped.role_distribution ?? wrapped.roleDistribution ?? fallbackWrapped.roleDistribution ?? {},
    permissions: wrapped.permissions ?? fallbackWrapped.permissions ?? [],
  };
}

export function normalizeStabilizationOperatorFatigue(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "operator_fatigue");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.operator_fatigue) ? fallbackSource.operator_fatigue : fallbackSource;
  const rows = arrayOrEmpty(wrapped.fatigue_rows ?? wrapped.fatigueRows ?? fallbackWrapped.fatigueRows);
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    fatigueScore: numberOrZero(wrapped.fatigue_score ?? wrapped.fatigueScore ?? fallbackWrapped.fatigueScore),
    warnings: arrayOrEmpty(wrapped.warnings ?? fallbackWrapped.warnings).map(stringOrEmpty),
    fatigueRows: rows.map((row, index) => ({
      operatorId: stringOrEmpty(row?.operator_id ?? row?.operatorId ?? `operator-${index + 1}`),
      workloadScore: numberOrZero(row?.workload_score ?? row?.workloadScore ?? row?.assigned),
      fatigueScore: numberOrZero(row?.fatigue_score ?? row?.fatigueScore),
      warning: stringOrEmpty(row?.warning || row?.note || row?.message),
      recommendation: stringOrEmpty(row?.recommendation || row?.action || row?.status),
      overdueReviews: numberOrZero(row?.overdue_reviews ?? row?.overdueReviews ?? row?.overdue),
      repeatedEscalations: numberOrZero(row?.repeated_escalations ?? row?.repeatedEscalations ?? row?.escalations),
      prolongedQueueExposure: numberOrZero(row?.prolonged_queue_exposure ?? row?.prolongedQueueExposure ?? row?.average_queue_age_minutes ?? row?.averageQueueAgeMinutes),
      focusSessionExhaustion: numberOrZero(row?.focus_session_exhaustion ?? row?.focusSessionExhaustion),
    })),
    workloadRebalanceRecommendations: arrayOrEmpty(wrapped.workload_rebalance_recommendations ?? wrapped.workloadRebalanceRecommendations ?? fallbackWrapped.workloadRebalanceRecommendations).map((row) =>
      stringOrEmpty(row?.recommendation || row?.reason || row?.action || row),
    ),
    signals: wrapped.signals ?? fallbackWrapped.signals ?? {},
  };
}

export function normalizeStabilizationOperatorFeedback(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "operator_feedback");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.operator_feedback) ? fallbackSource.operator_feedback : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    painPoints: arrayOrEmpty(wrapped.pain_points ?? wrapped.painPoints ?? fallbackWrapped.painPoints).map((item) => stringOrEmpty(item?.message || item?.value || item)),
    trendSummary: wrapped.trend_summary ?? wrapped.trendSummary ?? fallbackWrapped.trendSummary ?? {},
    feedbackItems: arrayOrEmpty(wrapped.feedback_items ?? wrapped.feedbackItems ?? fallbackWrapped.feedbackItems).map((row) => ({
      label: stringOrEmpty(row?.label || row?.title || row?.kind || row?.topic),
      value: stringOrEmpty(row?.value || row?.message || row?.detail || row?.severity),
    })),
    operationalSignals: wrapped.operational_signals ?? wrapped.operationalSignals ?? fallbackWrapped.operationalSignals ?? {},
  };
}

export function normalizeStabilizationRuntimeCleanup(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "runtime_cleanup");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.runtime_cleanup) ? fallbackSource.runtime_cleanup : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "fallback"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    dryRunOnly: Boolean(wrapped.dry_run_only ?? wrapped.dryRunOnly ?? fallbackWrapped.dryRunOnly ?? true),
    confirmed: Boolean(wrapped.confirmed ?? fallbackWrapped.confirmed),
    cleanupSummary: wrapped.cleanup_summary ?? wrapped.cleanupSummary ?? fallbackWrapped.cleanupSummary ?? {},
    wouldCleanup: arrayOrEmpty(wrapped.would_cleanup ?? wrapped.wouldCleanup ?? fallbackWrapped.wouldCleanup).map((row) => ({
      label: stringOrEmpty(row?.label || row?.name || row?.kind || row?.reason || row?.category || row?.path),
      count: numberOrZero(row?.count ?? 1),
    })),
    warnings: arrayOrEmpty(wrapped.warnings ?? fallbackWrapped.warnings).map(stringOrEmpty),
    blockers: arrayOrEmpty(wrapped.blockers ?? fallbackWrapped.blockers).map(stringOrEmpty),
  };
}

export function normalizeStabilizationDeploymentStability(payload, fallback = {}) {
  const { source, wrapped } = normalizeWrappedPayload(payload, "deployment_stability");
  const fallbackSource = isObject(fallback) ? fallback : {};
  const fallbackWrapped = isObject(fallbackSource.deployment_stability) ? fallbackSource.deployment_stability : fallbackSource;
  return {
    status: normalizeState(source.status || wrapped.status || fallbackSource.status, "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || wrapped.generated_at || wrapped.generatedAt || fallbackSource.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || wrapped.data_source || wrapped.dataSource || fallbackSource.dataSource, "runtime_fallback"),
    deploymentStabilityScore: numberOrZero(wrapped.deployment_stability_score ?? wrapped.deploymentStabilityScore ?? fallbackWrapped.deploymentStabilityScore),
    startupReadiness: wrapped.startup_readiness ?? wrapped.startupReadiness ?? fallbackWrapped.startupReadiness ?? {},
    runtimeIntegrity: wrapped.runtime_integrity ?? wrapped.runtimeIntegrity ?? fallbackWrapped.runtimeIntegrity ?? {},
    environmentSummary: wrapped.environment_summary ?? wrapped.environmentSummary ?? fallbackWrapped.environmentSummary ?? {},
    persistenceHealth: wrapped.persistence_health ?? wrapped.persistenceHealth ?? fallbackWrapped.persistenceHealth ?? {},
    queueSummary: wrapped.queue_summary ?? wrapped.queueSummary ?? fallbackWrapped.queueSummary ?? {},
    routeAvailability: wrapped.route_availability ?? wrapped.routeAvailability ?? fallbackWrapped.routeAvailability ?? {},
    routeNames: arrayOrEmpty(wrapped.route_names ?? wrapped.routeNames ?? fallbackWrapped.routeNames).map(stringOrEmpty),
    warnings: arrayOrEmpty(wrapped.warnings ?? fallbackWrapped.warnings).map(stringOrEmpty),
    startupBlockers: arrayOrEmpty(wrapped.startup_blockers ?? wrapped.startupBlockers ?? fallbackWrapped.startupBlockers).map(stringOrEmpty),
    blockers: arrayOrEmpty(wrapped.blockers ?? fallbackWrapped.blockers).map(stringOrEmpty),
    authAvailable: Boolean(wrapped.auth_available ?? wrapped.authAvailable ?? fallbackWrapped.authAvailable),
    persistenceAvailable: Boolean(wrapped.persistence_available ?? wrapped.persistenceAvailable ?? fallbackWrapped.persistenceAvailable),
    queueAvailable: Boolean(wrapped.queue_available ?? wrapped.queueAvailable ?? fallbackWrapped.queueAvailable),
    observabilityAvailable: Boolean(wrapped.observability_available ?? wrapped.observabilityAvailable ?? fallbackWrapped.observabilityAvailable),
  };
}

export function normalizeRuntimeReliability(payload, fallback = {}) {
  const source = isObject(payload) ? payload : {};
  const fallbackSource = isObject(fallback) ? fallback : {};
  const runtimeStability = normalizeStabilizationRuntime(source.runtimeStability ?? source.runtime_stability ?? {}, fallbackSource.runtimeStability ?? fallbackSource.runtime_stability ?? {});
  const fallbackHealth = normalizeStabilizationFallbackHealth(source.fallbackHealth ?? source.fallback_health ?? {}, fallbackSource.fallbackHealth ?? fallbackSource.fallback_health ?? {});
  const telemetryNoise = normalizeStabilizationTelemetryNoise(source.telemetryNoise ?? source.telemetry_noise ?? {}, fallbackSource.telemetryNoise ?? fallbackSource.telemetry_noise ?? {});
  const deploymentStability = normalizeStabilizationDeploymentStability(source.deploymentStability ?? source.deployment_stability ?? {}, fallbackSource.deploymentStability ?? fallbackSource.deployment_stability ?? {});
  return {
    status: normalizeState(source.status || fallbackSource.status || runtimeStability.status, runtimeStability.status || "degraded"),
    generatedAt: stringOrEmpty(source.generated_at || source.generatedAt || fallbackSource.generatedAt || runtimeStability.generatedAt),
    dataSource: normalizeState(source.data_source || source.dataSource || fallbackSource.dataSource || runtimeStability.dataSource, "runtime_fallback"),
    runtimeStability,
    fallbackHealth,
    telemetryNoise,
    deploymentStability,
    summary: {
      stabilityScore: runtimeStability.stabilityScore,
      fallbackActivations: fallbackHealth.fallbackActivations,
      noiseScore: telemetryNoise.noiseScore,
      deploymentScore: deploymentStability.deploymentStabilityScore,
    },
  };
}
