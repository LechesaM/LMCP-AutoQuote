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
