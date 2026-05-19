import { axiosAdapter } from "./axiosAdapter";
import { normalizeRFQWorkflowDetail, normalizeRFQWorkflowResponse, normalizeDashboardTelemetry } from "./normalize";
import useTelemetryStore from "../store/telemetryStore";

function buildFallbackRows() {
  const telemetry = normalizeDashboardTelemetry(useTelemetryStore.getState(), useTelemetryStore.getState());
  return telemetry.topHighProfitRfqs.map((item, index) => ({
    tenderId: `fallback-${index + 1}`,
    title: item.title,
    buyer: "Fallback buyer",
    province: item.province,
    qualificationState: index === 0 ? "GO" : "MANUAL_REVIEW",
    estimatedProfit: Number(String(item.profit).replace(/[^0-9.-]/g, "")) || 0,
    estimatedMargin: telemetry.avgMargin,
    riskLevel: index === 0 ? "low" : "medium",
    workflowStage: index === 0 ? "review_ready" : "approval_required",
    reviewStatus: index === 0 ? "review_ready" : "manual_review_required",
    pricingConfidence: 75,
    sourceTier: "Tier 2",
    submissionMethod: "email",
    dataSource: telemetry.dataSource || "static_seed",
    lastUpdated: telemetry.generatedAt || new Date().toISOString(),
  }));
}

export async function fetchRFQOperations() {
  const remote = await axiosAdapter("/operations/rfqs");
  if (remote?.rows) {
    return normalizeRFQWorkflowResponse(remote);
  }
  const rows = buildFallbackRows();
  return {
    status: "ok",
    generatedAt: new Date().toISOString(),
    dataSource: "static_seed",
    summary: {
      total: rows.length,
      go: rows.filter((row) => row.qualificationState === "GO").length,
      manualReview: rows.filter((row) => row.qualificationState === "MANUAL_REVIEW").length,
      reject: rows.filter((row) => row.qualificationState === "REJECT").length,
      dataSource: "static_seed",
    },
    rows,
  };
}

export async function fetchRFQDetail(tenderId) {
  const remote = await axiosAdapter(`/operations/rfqs/${encodeURIComponent(tenderId)}`);
  if (remote?.tender_id || remote?.tenderId) {
    return normalizeRFQWorkflowDetail(remote);
  }
  const rows = buildFallbackRows();
  const row = rows.find((item) => item.tenderId === tenderId) || rows[0];
  return normalizeRFQWorkflowDetail({
    status: "ok",
    generatedAt: new Date().toISOString(),
    dataSource: row?.dataSource || "static_seed",
    tenderId: row?.tenderId || tenderId,
    summary: {
      title: row?.title || "Unknown RFQ",
      buyer: row?.buyer || "Unknown",
      province: row?.province || "Unknown",
      workflowStage: row?.workflowStage || "unknown",
      reviewStatus: row?.reviewStatus || "manual_review_required",
    },
    qualificationSummary: {},
    riskSummary: {},
    pricingEvidence: {},
    pricingValidation: {},
    pricingTraceability: {},
    governanceSummary: {
      manual_approval_status: true,
      review_ready_status: row?.qualificationState === "GO",
      proof_capture_status: false,
      supervised_live_governance: true,
      manual_submission_confirmed: false,
      governance_compliance_score: 100,
    },
    workflowHistory: [],
    operationalWarnings: [],
    recommendationReasons: [],
    manualReviewTriggers: [],
    disqualificationTriggers: [],
    sourceHealth: {},
    dataSourceLabel: row?.dataSource || "static_seed",
  });
}
