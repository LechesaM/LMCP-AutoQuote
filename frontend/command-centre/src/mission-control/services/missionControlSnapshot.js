import { API_BASE } from "./missionControlApi.js";

const EMPTY_SNAPSHOT = {
  portals: [],
  harvestedCount: 0,
  provinceDistribution: {},
  radar: {},
  pipelineStages: {},
  aiScoring: {
    status: "not_configured",
    items: [],
  },
};

const PROVINCES = ["GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP"];

async function readJson(path, fallback) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`);
    }

    return await response.json();
  } catch {
    return fallback;
  }
}

function readCount(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function stringValue(value, fallback = "") {
  return value == null || value === "" ? fallback : String(value);
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function extractRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.opportunities)) return payload.opportunities;
  if (Array.isArray(payload?.rows)) return payload.rows;
  return [];
}

function compactStage(item) {
  const status = String(item?.submission_status || item?.pipeline_status || item?.status || "new").toLowerCase();
  if (status.includes("submitted")) return "Submitted";
  if (status.includes("pack") || status.includes("pdf") || status.includes("quote")) return "Quote Pack";
  if (status.includes("eligible") || status.includes("ready")) return "Ready";
  if (status.includes("reject") || status.includes("skip") || status.includes("fail")) return "Blocked";
  return "Harvested";
}

function provinceCode(item) {
  const raw = String(item?.province || item?.buyer_province || item?.location || item?.region || "").toUpperCase();
  if (raw.includes("GAUTENG") || raw === "GP") return "GP";
  if (raw.includes("FREE STATE") || raw === "FS") return "FS";
  if (raw.includes("KWAZULU") || raw.includes("KZN")) return "KZN";
  if (raw.includes("WESTERN CAPE") || raw === "WC") return "WC";
  if (raw.includes("EASTERN CAPE") || raw === "EC") return "EC";
  if (raw.includes("NORTHERN CAPE") || raw === "NC") return "NC";
  if (raw.includes("NORTH WEST") || raw === "NW") return "NW";
  if (raw.includes("MPUMALANGA") || raw === "MP") return "MP";
  if (raw.includes("LIMPOPO") || raw === "LP") return "LP";
  return "FS";
}

function normalizeOpportunities(rows) {
  return extractRows(rows).map((row, index) => ({
    id: stringValue(row?.id || row?.buyer_rfq_number || row?.rfq_number || row?.reference || `opportunity-${index}`),
    buyerRfqNumber: stringValue(row?.buyer_rfq_number || row?.rfq_number || row?.reference || row?.id || `RFQ-${index + 1}`),
    buyerName: stringValue(row?.buyer_name || row?.organisation || row?.department || row?.buyer || "Buyer"),
    province: provinceCode(row),
    stage: compactStage(row),
    profit: readCount(row?.total_profit || row?.estimated_profit || row?.profit || 0),
    quoteReady: Boolean(row?.quote_ready || compactStage(row) === "Ready" || compactStage(row) === "Quote Pack"),
    createdAt: stringValue(row?.created_at || row?.createdAt || ""),
  }));
}

function normalizePortals(payload) {
  const portals = safeArray(payload?.portals).map((portal, index) => ({
    name: stringValue(portal?.name || portal?.source || `Portal ${index + 1}`),
    status: stringValue(portal?.status || portal?.health || "unknown"),
    successRate: readCount(portal?.success_rate ?? portal?.successRate ?? 0),
  }));

  if (portals.length) {
    return portals;
  }

  return [
    { name: "eTenders", status: "monitored", successRate: 100 },
    { name: "SOE portals", status: "monitored", successRate: 100 },
    { name: "Municipal portals", status: "monitored", successRate: 100 },
    { name: "Provincial portals", status: "monitored", successRate: 100 },
  ];
}

function normalizeProvinceDistribution(telemetryDashboard, opportunities) {
  const rows = safeArray(telemetryDashboard?.province_distribution || telemetryDashboard?.provinceDistribution);
  if (rows.length) {
    const next = Object.fromEntries(PROVINCES.map((province) => [province, 0]));
    for (const row of rows) {
      const province = stringValue(row?.code || row?.province_code || row?.province, "").toUpperCase();
      const key = PROVINCES.includes(province) ? province : provinceCode(row);
      const value = readCount(row?.rfqs ?? row?.eligible ?? row?.value ?? 0);
      next[key] = value;
    }
    return next;
  }

  const next = Object.fromEntries(PROVINCES.map((province) => [province, 0]));
  for (const opportunity of opportunities) {
    next[opportunity.province] += 1;
  }
  return next;
}

function normalizePipelineStages(lifecycle, opportunities) {
  const queue = lifecycle?.queue_by_lifecycle_state || {};
  const liveCounts = {
    Harvested:
      readCount(queue.DISCOVERED || 0) +
      readCount(queue.QUALIFIED || 0) +
      readCount(queue.DOCUMENTS_ACQUIRED || 0) +
      readCount(queue.DOCUMENTS_PARSED || 0) +
      readCount(queue.PRICED || 0),
    Ready: readCount(queue.SUBMISSION_READY || 0),
    "Quote Pack": readCount(queue.QUOTE_PACK_READY || 0),
    Submitted: readCount(lifecycle?.proof_captured_rfqs || lifecycle?.proof_archive_count || 0),
    Blocked:
      readCount(queue.FAILED || 0) +
      readCount(queue.REVIEW_REQUIRED || 0) +
      readCount(queue.READY_FOR_RETRY || 0) +
      readCount(queue.REJECTED || 0),
  };

  if (Object.values(liveCounts).some((value) => Number(value || 0) > 0)) {
    return liveCounts;
  }

  const fallback = { Harvested: 0, Ready: 0, "Quote Pack": 0, Submitted: 0, Blocked: 0 };
  for (const opportunity of opportunities) {
    fallback[opportunity.stage] = (fallback[opportunity.stage] || 0) + 1;
  }
  return fallback;
}

function normalizeRadar({ radar, summary, telemetryDashboard, lifecycle, telemetry, opportunities, quoteReadyCount, submittedCount }) {
  const source = radar?.radar || radar || {};
  const lifecycleHealthScore = readCount(source.lifecycle_health_score ?? lifecycle?.lifecycle_health_score ?? 0);
  const systemResilienceScore = readCount(source.system_resilience_score ?? telemetry?.system_resilience_score ?? 0);
  const workerOnline = Boolean(source.worker_online ?? telemetry?.worker_online ?? false);
  const onlineWorkers = readCount(source.online_workers ?? source.onlineWorkers ?? telemetry?.worker_online_count ?? 0);
  const queueBacklog = readCount(source.queue_backlog ?? telemetry?.queue_backlog?.total_backlog ?? 0);
  const failedRfqs = readCount(source.failed_rfqs ?? lifecycle?.failed_rfqs ?? 0);
  const reviewRequired = readCount(source.review_required ?? lifecycle?.review_required_rfqs ?? lifecycle?.review_required_count ?? 0);
  const proofCaptured = readCount(source.proof_captured ?? lifecycle?.proof_captured_rfqs ?? lifecycle?.proof_archive_count ?? 0);
  const estimatedMonthlyCapacity = readCount(source.estimated_monthly_capacity ?? lifecycle?.estimated_monthly_capacity ?? 0);
  const uploadReadinessScore = readCount(source.upload_readiness_score ?? 0);

  return {
    status: stringValue(radar?.status || source.status || "ok"),
    serviceVersion: stringValue(radar?.service_version || radar?.serviceVersion || source.service_version || source.serviceVersion || source.status || "active"),
    sources: readCount(summary?.cards?.total_opportunities, 0) || readCount(telemetryDashboard?.total_harvested_rfqs, 0) || opportunities.length,
    eligible: readCount(summary?.cards?.qualified_rfqs, 0) || quoteReadyCount,
    lifecycleHealthScore,
    systemResilienceScore,
    workerOnline,
    onlineWorkers,
    queueBacklog,
    failedRfqs,
    reviewRequired,
    proofCaptured,
    estimatedMonthlyCapacity,
    uploadReadinessScore,
    statusLabel: stringValue(radar?.status || source.status || "active"),
    backendStatus: workerOnline || lifecycleHealthScore >= 90 ? "healthy" : "degraded",
    generatedAt: stringValue(radar?.generated_at || radar?.generatedAt || source.generated_at || source.generatedAt || ""),
  };
}

function normalizeAiScoring() {
  return {
    status: "not_configured",
    items: [],
  };
}

function normalizeTrend(submissionSummary, submittedCount) {
  return [
    { label: "D", value: readCount(submissionSummary?.today ?? submissionSummary?.daily ?? submissionSummary?.submitted_today ?? Math.min(submittedCount, 4), Math.min(submittedCount, 4)) },
    { label: "W", value: readCount(submissionSummary?.week ?? submissionSummary?.weekly ?? submissionSummary?.submitted_this_week ?? Math.min(submittedCount, 14), Math.min(submittedCount, 14)) },
    { label: "M", value: readCount(submissionSummary?.month ?? submissionSummary?.monthly ?? submissionSummary?.submitted_this_month ?? submittedCount, submittedCount) },
  ];
}

function normalizeAlerts({ backendStatus, systemOn, blockedCount }) {
  return [
    backendStatus !== "healthy" && `Backend health: ${backendStatus || "unknown"}`,
    !systemOn && "Autonomous engine is OFF",
    blockedCount > 0 && `${blockedCount} tender(s) blocked or failed`,
  ].filter(Boolean);
}

export async function fetchMissionControlSnapshot() {
  const [
    health,
    auto,
    summary,
    opportunities,
    submissionSummary,
    submissionProfit,
    submissionHistory,
    portal,
    radar,
    policy,
    lifecycle,
    lifecycleAnalytics,
    lifecycleTelemetry,
    telemetryDashboard,
  ] = await Promise.all([
    readJson("/health", {}),
    readJson("/v48-autonomous/status", {}),
    readJson("/dashboard/summary", {}),
    readJson("/opportunities", []),
    readJson("/submission-analytics/summary", {}),
    readJson("/submission-analytics/profit", {}),
    readJson("/submission-history/recent", []),
    readJson("/portal-health", {}),
    readJson("/radar/status", {}),
    readJson("/v48-autonomous/policy", {}),
    readJson("/rfq-lifecycle/mission-control", {}),
    readJson("/rfq-lifecycle/analytics", {}),
    readJson("/rfq-lifecycle/telemetry", {}),
    readJson("/telemetry/dashboard", {}),
  ]);

  const normalizedOpportunities = normalizeOpportunities(opportunities);
  const harvestedCount =
    readCount(telemetryDashboard?.total_harvested_rfqs ?? telemetryDashboard?.totalHarvested ?? 0) ||
    readCount(lifecycle?.total_rfqs ?? 0) ||
    readCount(summary?.cards?.total_opportunities ?? normalizedOpportunities.length, normalizedOpportunities.length);

  const quoteReadyCount =
    readCount(lifecycle?.queue_by_lifecycle_state?.QUOTE_PACK_READY ?? 0) ||
    readCount(lifecycle?.queue_by_lifecycle_state?.SUBMISSION_READY ?? 0) ||
    normalizedOpportunities.filter((item) => item.quoteReady).length;

  const submittedCount =
    readCount(lifecycle?.proof_captured_rfqs ?? lifecycle?.proof_archive_count ?? 0) ||
    readCount(submissionSummary?.submitted ?? submissionSummary?.total_submitted ?? submissionSummary?.submitted_count ?? 0);

  const blockedCount =
    readCount(lifecycle?.failed_rfqs ?? lifecycle?.review_required_rfqs ?? lifecycle?.review_required_count ?? 0) ||
    normalizedOpportunities.filter((item) => item.stage === "Blocked").length;

  const profitTotal =
    readCount(submissionProfit?.total_profit ?? submissionProfit?.profit ?? submissionProfit?.estimated_profit ?? 0) ||
    safeArray(submissionHistory).reduce((sum, item) => sum + readCount(item?.total_profit || item?.profit || 0), 0);

  const queueByState = lifecycle?.queue_by_lifecycle_state || {};
  const systemControl = lifecycle?.safety?.system_control || {};
  const effectiveStatus = String(systemControl.effective_system_status || policy?.policy?.mode || "controlled").toLowerCase();
  const systemOn = Boolean(
    systemControl.system_on !== undefined
      ? systemControl.system_on
      : effectiveStatus === "on" || effectiveStatus === "controlled"
        ? true
        : policy?.policy?.enabled ?? auto?.enabled ?? true,
  );

  const backendStatus =
    health?.status === "healthy" || lifecycleTelemetry?.worker_online || (radar?.radar || radar || {}).worker_online
      ? "healthy"
      : health?.status || "unknown";

  const displayMode =
    lifecycle?.safety?.system_control?.effective_system_status ||
    policy?.policy?.mode ||
    (systemOn ? "controlled" : "off");

  const pipelineStages = normalizePipelineStages(lifecycle, normalizedOpportunities);
  const provinceDistribution = normalizeProvinceDistribution(telemetryDashboard, normalizedOpportunities);
  const portals = normalizePortals(portal);
  const radarSnapshot = normalizeRadar({
    radar,
    summary,
    telemetryDashboard,
    lifecycle,
    telemetry: lifecycleTelemetry,
    opportunities: normalizedOpportunities,
    quoteReadyCount,
    submittedCount,
  });

  return {
    ...EMPTY_SNAPSHOT,
    status: "ready",
    generatedAt: new Date().toISOString(),
    portals,
    harvestedCount,
    provinceDistribution,
    radar: radarSnapshot,
    pipelineStages,
    aiScoring: normalizeAiScoring(),
    opportunities: normalizedOpportunities,
    history: safeArray(submissionHistory),
    summary,
    submissionSummary,
    submissionProfit,
    health,
    auto,
    portal,
    radar,
    policy,
    lifecycle,
    lifecycleAnalytics,
    lifecycleTelemetry,
    telemetryDashboard,
    metrics: {
      backendStatus,
      displayMode,
      systemOn,
      quoteReadyCount,
      submittedCount,
      blockedCount,
      profitTotal,
      trend: normalizeTrend(submissionSummary, submittedCount),
      alerts: normalizeAlerts({ backendStatus, systemOn, blockedCount }),
      portalStatus: portals.length ? "live" : "fallback",
      topOpps: normalizedOpportunities.slice(0, 9),
    },
  };
}

export { EMPTY_SNAPSHOT };
