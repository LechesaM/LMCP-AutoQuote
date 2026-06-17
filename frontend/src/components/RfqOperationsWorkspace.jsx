import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  FileSpreadsheet,
  FileText,
  Filter,
  FolderOpen,
  History,
  PauseCircle,
  Search,
  ShieldAlert,
  ThumbsUp,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";

const REQUEST_TIMEOUT_MS = 8000;

const RFQ_ENDPOINTS = [
  "/operations/rfqs",
  "/rfq-lifecycle/status",
  "/rfq-lifecycle/recent",
  "/rfq-lifecycle/report",
  "/opportunities",
  "/submission-history/recent",
  "/submission-proof/latest",
  "/portal-submission/status",
  "/health",
];

const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
const DRAWER_TABS = ["Overview", "Manual Pricing", "Documents", "BOQ / Pricing", "Qualification", "Submission Readiness", "Proofs / Audit"];

const DEMO_RFQS = [
  {
    id: "demo-rfq-operations",
    reference: "RFQ-DEMO-001",
    title: "Supply and delivery RFQ workspace preview",
    buyer: "Demo Buyer",
    province: "GP",
    closing_date: new Date(Date.now() + 4 * 86400000).toISOString(),
    source: "frontend fallback",
    status: "Review Required",
    estimated_value: 145000,
    estimated_profit: 36250,
    margin_percent: 25,
    documents: [{ name: "Buyer RFQ form.pdf", type: "Buyer Form" }],
    boqs: [{ name: "Bill of quantities.xlsx", type: "BOQ" }],
    pricing_schedules: [{ name: "Pricing schedule.xlsx", type: "Pricing Schedule" }],
    missing_returnables: ["Signed declaration", "Tax compliance PIN"],
    qualification_score: 74,
    quote_readiness_score: 82,
    submission_readiness_score: 58,
    rfq_discovered: true,
    buyer_pack_downloaded: true,
    buyer_pack_status: "complete",
    boq_detected: true,
    boq_status: "complete",
    pricing_schedule_detected: true,
    pricing_schedule_status: "complete",
    returnables_detected: true,
    returnables_status: "complete",
    quote_pack_generated: true,
    quote_pack_status: "complete",
    quote_pack_readiness_score: 100,
    risks: ["Demo fallback data shown because live RFQs did not load"],
    recommended_action: "Mark for review",
    proofs: [],
    audit: [],
    _demo: true,
    _sources: ["frontend fallback"],
  },
];

function safeText(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number") return String(value);
  return fallback;
}

function pick(obj, keys, fallback = undefined) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}

function asArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    return value
      .split(/\n|;|\|/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [value];
}

function slug(value) {
  return safeText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90);
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function normalizeNumber(value, fallback = 0) {
  if (value === undefined || value === null || value === "") return fallback;
  const n = Number(String(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? n : fallback;
}

function normalizeScore(value, fallback = 0) {
  const n = normalizeNumber(value, fallback);
  if (n <= 1 && n > 0) return Math.round(n * 100);
  return Math.max(0, Math.min(100, Math.round(n)));
}

function coerceBool(value, fallback = false) {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  const raw = safeText(value, "").toLowerCase();
  if (!raw) return fallback;
  return ["1", "true", "yes", "y", "on", "complete", "completed", "ok", "verified"].includes(raw);
}

function statusTone(status) {
  const raw = safeText(status, "").toLowerCase();
  if (["complete", "downloaded", "detected", "generated", "ready"].includes(raw)) return "green";
  if (raw === "partial") return "amber";
  if (raw === "failed") return "red";
  return "neutral";
}

function normalizeComponentStatus(value, complete, failed, attempted, completeLabel = "downloaded") {
  const raw = safeText(value, "").toLowerCase();
  if (["downloaded", "detected", "generated", "failed", "not_attempted"].includes(raw)) return raw;
  if (complete) return completeLabel;
  if (failed) return "failed";
  return "not_attempted";
}

function lifecycleTone(stage) {
  const raw = safeText(stage, "").toLowerCase();
  if (raw.includes("submission")) return "green";
  if (raw.includes("quote ready") || raw.includes("quote pack generated")) return "blue";
  if (raw.includes("detected") || raw.includes("acquired")) return "amber";
  if (raw.includes("discovered")) return "neutral";
  return "neutral";
}

function normalizeLifecycleStage(record, intelligence) {
  const explicit = safeText(
    pick(record, ["lifecycle_stage_label", "lifecycle_stage"], pick(intelligence, ["lifecycle_stage"], "")),
    "",
  );
  if (explicit) return explicit;
  const current = safeText(pick(record, ["current_state", "lifecycle_state", "pipeline_status", "stage", "submission_status"]), "").toUpperCase();
  if (current.includes("SUBMISSION")) return "SUBMISSION READY";
  if (current.includes("QUOTE_PACK") || current.includes("APPROVAL")) return "QUOTE READY";
  if (current.includes("PRICING_VERIFIED")) return "QUOTE PACK GENERATED";
  if (current.includes("PRICED")) return "PRICING DETECTED";
  if (current.includes("DOCUMENTS_PARSED")) return "BOQ DETECTED";
  if (current.includes("DOCUMENTS_ACQUIRED")) return "DOCUMENTS CLASSIFIED";
  if (current.includes("BUYER_PACK")) return "BUYER PACK ACQUIRED";
  if (coerceBool(pick(record, ["buyer_pack_downloaded"], pick(intelligence, ["buyer_pack_downloaded"], false)))) return "BUYER PACK ACQUIRED";
  return "DISCOVERED";
}

function normalizeProvince(value) {
  const raw = safeText(value, "Unknown").toUpperCase();
  if (raw.includes("GAUTENG") || raw === "GP") return "GP";
  if (raw.includes("FREE STATE") || raw === "FS") return "FS";
  if (raw.includes("KWAZULU") || raw.includes("KZN")) return "KZN";
  if (raw.includes("WESTERN CAPE") || raw === "WC") return "WC";
  if (raw.includes("EASTERN CAPE") || raw === "EC") return "EC";
  if (raw.includes("NORTHERN CAPE") || raw === "NC") return "NC";
  if (raw.includes("NORTH WEST") || raw === "NW") return "NW";
  if (raw.includes("MPUMALANGA") || raw === "MP") return "MP";
  if (raw.includes("LIMPOPO") || raw === "LP") return "LP";
  return raw && raw !== "UNKNOWN" ? raw.slice(0, 18) : "Unknown";
}

function normalizeStatus(value, record = {}) {
  const raw = safeText(value || record.pipeline_status || record.lifecycle_state || record.stage || record.submission_status, "Discovered");
  const lower = raw.toLowerCase();
  const reviewPricing = safeText(pick(record, ["pricing_review_status", "manual_pricing_status"]), "").toLowerCase();
  if (lower.includes("pricing_required") || reviewPricing.includes("review_required_pricing") || safeText(pick(record, ["manual_pricing_required"]), "").toLowerCase() === "true") {
    return "Manual Pricing Required";
  }
  if (lower.includes("pricing_verified") || reviewPricing.includes("pricing_verified") || lower.includes("pricing verified")) {
    return "Pricing Verified";
  }
  if (lower.includes("submission_ready_manual") || lower.includes("submission ready manual")) return "Submission Ready (Manual)";
  if (lower.includes("submit") || lower.includes("proof")) return "Submitted";
  if (lower.includes("ready") && lower.includes("quote")) return "Quote Ready";
  if (lower.includes("submission") && lower.includes("ready")) return "Submission Ready";
  if (lower.includes("review")) return "Review Required";
  if (lower.includes("hold")) return "Hold";
  if (lower.includes("reject") || lower.includes("fail") || lower.includes("blocked")) return "Blocked";
  if (lower.includes("price") || lower.includes("boq")) return "Pricing";
  if (lower.includes("qual")) return "Qualified";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeArtifact(value, type = "Document") {
  if (!value) return null;
  if (typeof value === "string") {
    return { name: value.split("/").pop() || value, url: value.startsWith("http") || value.startsWith("/") ? value : "", type };
  }
  if (typeof value !== "object") return null;
  const url = safeText(pick(value, ["url", "href", "path", "file_path", "local_path", "download_url", "source_url"]));
  const name =
    safeText(pick(value, ["name", "filename", "file_name", "title", "label", "document_name"])) ||
    (url ? url.split("/").pop() : type);
  return {
    name,
    url,
    type: safeText(pick(value, ["type", "document_type", "category"]), type),
    status: safeText(pick(value, ["status", "state"]), ""),
  };
}

function collectArtifacts(record, keys, type) {
  const direct = keys.flatMap((key) => asArray(record?.[key]));
  return uniqueBy(
    direct.map((item) => normalizeArtifact(item, type)).filter(Boolean),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function inferArtifacts(allDocuments, pattern, type) {
  return uniqueBy(
    allDocuments
      .filter((doc) => pattern.test(`${doc.name} ${doc.type}`))
      .map((doc) => ({ ...doc, type })),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function isRfqLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(rfq|tender|opportunit|buyer|closing|quote|submission|boq|pricing|document|reference|title|description)/.test(keys);
}

function collectObjectRecords(payload, sourcePath) {
  const out = [];
  const seen = new Set();

  function walk(value, depth = 0, key = "") {
    if (depth > 5 || value === null || value === undefined) return;
    if (Array.isArray(value)) {
      value.forEach((item) => walk(item, depth + 1, key));
      return;
    }
    if (typeof value !== "object") return;

    if (isRfqLike(value)) {
      const sig = `${sourcePath}:${safeText(pick(value, ["id", "rfq_id", "reference", "rfq_number", "buyer_rfq_number", "title", "description"]), JSON.stringify(Object.keys(value).slice(0, 12)))}`;
      if (!seen.has(sig)) {
        seen.add(sig);
        out.push({ ...value, _sourcePath: sourcePath });
      }
    }

    Object.entries(value).forEach(([childKey, childValue]) => {
      if (childKey.startsWith("_")) return;
      walk(childValue, depth + 1, childKey);
    });
  }

  walk(payload);
  return out;
}

function deriveScores(record, missingReturnables, boqs, pricingSchedules, documents) {
  const explicitQualification = pick(record, ["qualification_score", "eligibility_score", "eligible_score", "score"]);
  const explicitQuote = pick(record, ["quote_readiness_score", "quote_score", "pricing_readiness_score"]);
  const explicitSubmission = pick(record, ["submission_readiness_score", "upload_readiness_score", "readiness_score"]);

  const status = normalizeStatus(pick(record, ["status", "lifecycle_state", "stage"]), record).toLowerCase();
  const baseQualification = status.includes("blocked") ? 32 : status.includes("qualified") || status.includes("ready") ? 78 : 62;
  const documentScore = Math.min(30, documents.length * 8);
  const pricingScore = (boqs.length ? 24 : 0) + (pricingSchedules.length ? 24 : 0);
  const missingPenalty = Math.min(45, missingReturnables.length * 12);

  const qualification = explicitQualification !== undefined ? normalizeScore(explicitQualification) : Math.max(0, baseQualification - Math.min(30, missingPenalty / 2));
  const quote = explicitQuote !== undefined ? normalizeScore(explicitQuote) : Math.max(0, Math.min(100, 38 + documentScore + pricingScore - missingPenalty));
  const submission = explicitSubmission !== undefined ? normalizeScore(explicitSubmission) : Math.max(0, Math.min(100, quote - missingPenalty + (status.includes("submitted") ? 25 : 0)));

  return { qualification, quote, submission };
}

function normalizeRisks(record, missingReturnables, boqs, pricingSchedules) {
  const explicit = asArray(pick(record, ["risks", "risk_flags", "alerts", "warnings", "blockers", "blocker_reasons", "review_reasons", "qualification_reasons"]))
    .map((item) => safeText(item))
    .filter(Boolean);
  const inferred = [];
  if (missingReturnables.length) inferred.push(`${missingReturnables.length} returnable(s) missing`);
  if (!boqs.length) inferred.push("BOQ not detected");
  if (!pricingSchedules.length) inferred.push("Pricing schedule not detected");
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase()).slice(0, 8);
}

function normalizeRfqRecord(record, sourcePath) {
  const reference = safeText(
    pick(record, ["reference", "rfq_reference", "rfq_number", "buyer_rfq_number", "bid_number", "tender_number", "id", "rfq_id"]),
    "RFQ",
  );
  const title = safeText(pick(record, ["title", "description", "name", "opportunity_title", "tender_title", "subject"]), reference);
  const buyer = safeText(pick(record, ["buyer", "buyer_name", "department", "organisation", "organization", "client", "entity"]), "Unknown Buyer");
  const province = normalizeProvince(pick(record, ["province", "buyer_province", "region", "location"]));
  const allDocuments = uniqueBy(
    [
      ...collectArtifacts(record, ["documents", "docs", "files", "attachments", "downloaded_documents", "source_documents", "buyer_forms", "returnable_forms"], "Document"),
      ...collectArtifacts(record, ["rfq_document", "rfq_pdf", "form", "buyer_form"], "Buyer Form"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const boqs = uniqueBy(
    [
      ...collectArtifacts(record, ["boqs", "boq", "bill_of_quantities", "bill_of_quantity"], "BOQ"),
      ...inferArtifacts(allDocuments, /\b(boq|bill[-_\s]*of[-_\s]*quantit)/i, "BOQ"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const pricingSchedules = uniqueBy(
    [
      ...collectArtifacts(record, ["pricing_schedules", "pricing_schedule", "price_schedule", "pricing", "price_list", "rates"], "Pricing Schedule"),
      ...inferArtifacts(allDocuments, /\b(pric(e|ing)|schedule|rates?|quotation[-_\s]*form)\b/i, "Pricing Schedule"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const technicalSpecFiles = uniqueBy(
    [
      ...collectArtifacts(record, ["technical_spec_files", "specification_files", "specification_paths"], "Technical Specification"),
      ...inferArtifacts(allDocuments, /\b(specification|scope of work|tor|technical)\b/i, "Technical Specification"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const returnableFiles = uniqueBy(
    [
      ...collectArtifacts(record, ["returnable_files", "returnable_forms", "buyer_forms", "sbd_files"], "Returnable"),
      ...inferArtifacts(allDocuments, /\b(sbd|returnable|declaration|compliance|forms?)\b/i, "Returnable"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const missingReturnables = uniqueBy(
    asArray(pick(record, ["missing_returnables", "missing_documents", "missing_forms", "returnables_missing", "upload_missing", "readiness_gaps", "blocker_reasons"]))
      .map((item) => safeText(typeof item === "object" ? pick(item, ["name", "label", "field", "document", "reason"]) : item))
      .filter(Boolean),
    (item) => item.toLowerCase(),
  );
  const blockerReasons = uniqueBy(
    asArray(pick(record, ["blocker_reasons", "review_reasons"]))
      .map((item) => safeText(item))
      .filter(Boolean),
    (item) => item.toLowerCase(),
  );
  const intelligence = record?.document_intelligence && typeof record.document_intelligence === "object" ? record.document_intelligence : {};
  const eligibilityFailureReason = safeText(
    pick(record, ["eligibility_failure_reason", "eligibility_reason", "rejection_reason", "qualification_reason"], pick(intelligence, ["eligibility_failure_reason"], "")),
    "",
  );
  const buyerPackDownloaded = coerceBool(pick(record, ["buyer_pack_downloaded", "buyer_pack_verified"], pick(intelligence, ["buyer_pack_downloaded", "buyer_pack_verified"], false)));
  const buyerPackDownloadFailed = coerceBool(pick(record, ["buyer_pack_download_failed"], pick(intelligence, ["buyer_pack_download_failed"], false)));
  const buyerPackDownloadTimestamp = safeText(
    pick(record, ["buyer_pack_download_timestamp"], pick(intelligence, ["buyer_pack_download_timestamp"], "")),
    "",
  );
  const buyerPackSource = safeText(pick(record, ["buyer_pack_source"], pick(intelligence, ["buyer_pack_source"], "")), "");
  const downloadFailureReason = safeText(
    pick(record, ["download_failure_reason", "buyer_pack_download_failure_reason", "document_acquisition_failure_reason"], pick(intelligence, ["download_failure_reason"], "")),
    "",
  );
  const boqDetected = coerceBool(pick(record, ["boq_detected"], pick(intelligence, ["boq_detected"], boqs.length > 0)));
  const pricingScheduleDetected = coerceBool(pick(record, ["pricing_schedule_detected"], pick(intelligence, ["pricing_schedule_detected"], pricingSchedules.length > 0)));
  const returnablesDetected = coerceBool(pick(record, ["returnables_detected"], pick(intelligence, ["returnables_detected"], returnableFiles.length > 0)));
  const extractionFailureReason = safeText(
    pick(record, ["extraction_failure_reason"], pick(intelligence, ["extraction_failure_reason"], "")),
    "",
  );
  const quotePackGenerated = coerceBool(
    pick(record, ["quote_pack_generated"], pick(intelligence, ["quote_pack_generated"], Boolean(pick(record, ["quote_pack_path", "quote_pack_workspace", "quote_pack_dir", "quote_pack_json_path"], "")))),
  );
  const buyerPackStatus = normalizeComponentStatus(
    pick(record, ["buyer_pack_status"], pick(intelligence, ["buyer_pack_status"], "")),
    buyerPackDownloaded,
    buyerPackDownloadFailed,
    Boolean(buyerPackDownloaded || buyerPackDownloadFailed || buyerPackDownloadTimestamp || buyerPackSource || downloadFailureReason),
    "downloaded",
  );
  const boqStatus = normalizeComponentStatus(
    pick(record, ["boq_status"], pick(intelligence, ["boq_status"], "")),
    boqDetected,
    Boolean(buyerPackDownloaded && !boqDetected && (pick(record, ["document_intelligence_report_path", "document_parse_summary_path"], "") || pick(intelligence, ["extraction_failure_reason"], ""))),
    Boolean(boqDetected || buyerPackDownloaded || extractionFailureReason),
    "detected",
  );
  const pricingScheduleStatus = normalizeComponentStatus(
    pick(record, ["pricing_schedule_status"], pick(intelligence, ["pricing_schedule_status"], "")),
    pricingScheduleDetected,
    Boolean(buyerPackDownloaded && !pricingScheduleDetected && (pick(record, ["document_intelligence_report_path", "document_parse_summary_path"], "") || pick(intelligence, ["extraction_failure_reason"], ""))),
    Boolean(pricingScheduleDetected || buyerPackDownloaded || extractionFailureReason),
    "detected",
  );
  const returnablesStatus = normalizeComponentStatus(
    pick(record, ["returnables_status"], pick(intelligence, ["returnables_status"], "")),
    returnablesDetected,
    Boolean(buyerPackDownloaded && !returnablesDetected && (pick(record, ["document_intelligence_report_path", "document_parse_summary_path"], "") || pick(intelligence, ["extraction_failure_reason"], ""))),
    Boolean(returnablesDetected || buyerPackDownloaded || extractionFailureReason),
    "detected",
  );
  const quotePackStatus = normalizeComponentStatus(
    pick(record, ["quote_pack_status"], pick(intelligence, ["quote_pack_status"], "")),
    quotePackGenerated,
    Boolean(pick(record, ["quote_pack_generation_failure_reason", "quote_pack_failure_reason"], pick(intelligence, ["quote_pack_generation_failure_reason"], ""))),
    Boolean(quotePackGenerated || buyerPackDownloaded || boqDetected || pricingScheduleDetected || returnablesDetected),
    "generated",
  );
  const readinessScore = normalizeScore(pick(record, ["acquisition_readiness_score", "quote_pack_readiness_score", "quote_pack_readiness_pct"], pick(intelligence, ["acquisition_readiness_score", "quote_pack_readiness_score"], 0)));
  const estimatedValue = normalizeNumber(pick(record, ["estimated_value", "value", "contract_value", "budget", "amount"]));
  const estimatedProfit = normalizeNumber(pick(record, ["estimated_profit", "profit", "total_profit", "gross_profit"]));
  const marginPercent = normalizeNumber(pick(record, ["margin_percent", "margin", "profit_margin"]), estimatedValue ? (estimatedProfit / estimatedValue) * 100 : 0);
  const scores = deriveScores(record, missingReturnables, boqs, pricingSchedules, allDocuments);
  const risks = normalizeRisks(record, missingReturnables, boqs, pricingSchedules);
  const id = slug(pick(record, ["id", "rfq_id"], "") || `${reference}-${title}`) || crypto.randomUUID();
  const lifecycleStage = normalizeLifecycleStage(record, intelligence);
  const status = lifecycleStage;
  const documentConfidenceScore = normalizeScore(pick(record, ["document_confidence_score", "document_acquisition_confidence", "confidence", "confidence_score"]));
  const pricingReviewStatus = safeText(pick(record, ["pricing_review_status", "manual_pricing_status"]), "");
  const manualPricingRequiredReason = safeText(pick(record, ["manual_pricing_required_reason"]), "");
  const pricingAction = safeText(pick(record, ["pricing_action", "pricing_review_action"]), "");
  const buyerPackPath = safeText(pick(record, ["buyer_pack_path", "live_buyer_pack_path"]), "");
  const quotePackPath = safeText(pick(record, ["quote_pack_path", "quote_pack_workspace", "quote_pack_dir"]), "");
  const manualPricingPath = safeText(pick(record, ["manual_pricing_path"]), "");
  const pricingVerificationStatus = safeText(pick(record, ["pricing_verification_status"]), "");
  const manualPricingRequiredValue = pick(record, ["manual_pricing_required"]);
  const currentState = safeText(pick(record, ["current_state", "lifecycle_state", "pipeline_status", "stage", "submission_status"]), "");
  const proofPath = safeText(pick(record, ["proof_path", "submission_proof_path", "proof_file", "proof_manifest"]), "");
  const proofIndexedValue = pick(record, ["proof_indexed"]);
  const proofIndexed = typeof proofIndexedValue === "boolean" ? proofIndexedValue : Boolean(proofPath);
  const submissionChecklistStatus = safeText(
    pick(record, ["submission_checklist_status", "manual_submission_status", "submission_status"]),
    currentState === "PROOF_CAPTURED" ? "completed" : "",
  );
  const recommendedAction =
    safeText(pick(record, ["recommended_action", "next_action", "operator_action"])) ||
    pricingAction ||
    (pricingReviewStatus === "REVIEW_REQUIRED_PRICING" ? "Prepare manual pricing schedule" : "") ||
    (scores.submission >= 80 ? "Approve for quote prep" : risks.length ? "Mark for review" : "Continue qualification");

  return {
    id,
    reference,
    title,
    buyer,
    province,
    closing_date: safeText(pick(record, ["closing_date", "closing", "close_date", "deadline", "closing_datetime"])),
    source: safeText(pick(record, ["source", "portal", "origin"]), sourcePath),
    current_state: currentState,
    status,
    pricing_review_status: pricingReviewStatus,
    manual_pricing_required: typeof manualPricingRequiredValue === "boolean" ? manualPricingRequiredValue : safeText(manualPricingRequiredValue, "").toLowerCase() === "true",
    manual_pricing_required_reason: manualPricingRequiredReason,
    pricing_action: pricingAction,
    pricing_verification_status: pricingVerificationStatus,
    manual_pricing_path: manualPricingPath,
    buyer_pack_path: buyerPackPath,
    quote_pack_path: quotePackPath,
    proof_path: proofPath,
    proof_indexed: proofIndexed,
    submission_checklist_status: submissionChecklistStatus,
    estimated_value: estimatedValue,
    estimated_profit: estimatedProfit,
    margin_percent: marginPercent,
    document_confidence_score: documentConfidenceScore,
    document_verification_status: safeText(pick(record, ["document_verification_status"]), documentConfidenceScore >= 75 ? "verified" : "pending"),
    rfq_discovered: coerceBool(pick(record, ["rfq_discovered"], pick(intelligence, ["rfq_discovered"], true)), true),
    buyer_pack_downloaded: buyerPackDownloaded,
    buyer_pack_download_failed: buyerPackDownloadFailed,
    buyer_pack_download_timestamp: buyerPackDownloadTimestamp,
    buyer_pack_source: buyerPackSource,
    download_failure_reason: downloadFailureReason,
    boq_detected: boqDetected,
    pricing_schedule_detected: pricingScheduleDetected,
    returnables_detected: returnablesDetected,
    extraction_failure_reason: extractionFailureReason,
    eligibility_failure_reason: eligibilityFailureReason,
    quote_pack_generated: quotePackGenerated,
    acquisition_readiness_score: readinessScore,
    quote_pack_readiness_score: readinessScore,
    buyer_pack_status: buyerPackStatus,
    boq_status: boqStatus,
    pricing_schedule_status: pricingScheduleStatus,
    returnables_status: returnablesStatus,
    quote_pack_status: quotePackStatus,
    lifecycle_stage: lifecycleStage,
    lifecycle_stage_label: lifecycleStage,
    quote_pack_readiness_components: pick(record, ["quote_pack_readiness_components"], pick(intelligence, ["quote_pack_readiness_components"], {
      buyer_pack: buyerPackDownloaded ? 20 : 0,
      boq: boqDetected ? 20 : 0,
      pricing_schedule: pricingScheduleDetected ? 20 : 0,
      returnables: returnablesDetected ? 20 : 0,
      quote_pack: quotePackGenerated ? 20 : 0,
    })),
    quote_candidate_status: safeText(
      pick(record, ["quote_candidate_status"]),
      pricingReviewStatus === "REVIEW_REQUIRED_PRICING" ? "manual_pricing_required" : "",
    ),
    blocker_reasons: blockerReasons,
    documents: allDocuments,
    boqs,
    pricing_schedules: pricingSchedules,
    technical_spec_files: technicalSpecFiles,
    returnable_files: returnableFiles,
    manual_pricing_line_items: asArray(pick(record, ["manual_pricing_line_items", "pricing_line_items"])),
    manual_pricing_totals: pick(record, ["manual_pricing_totals", "pricing_totals"], {}),
    manual_pricing_validation: pick(record, ["manual_pricing_validation"], {}),
    missing_returnables: missingReturnables,
    qualification_score: scores.qualification,
    quote_readiness_score: scores.quote,
    submission_readiness_score: scores.submission,
    risks,
    recommended_action: recommendedAction,
    proofs: collectArtifacts(record, ["proofs", "submission_proofs", "proof_files", "receipts"], "Proof"),
    audit: asArray(pick(record, ["audit", "events", "history", "timeline"])).filter((item) => item && typeof item === "object").slice(0, 8),
    _sources: [sourcePath],
    _raw: record,
  };
}

function mergeRfqs(records) {
  const map = new Map();
  for (const record of records) {
    const key = slug(record.reference !== "RFQ" ? record.reference : record.title) || record.id;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, record);
      continue;
    }
    map.set(key, {
      ...existing,
      ...Object.fromEntries(Object.entries(record).filter(([, value]) => value !== "" && value !== 0 && value !== undefined && value !== null)),
      id: existing.id,
      reference: existing.reference !== "RFQ" ? existing.reference : record.reference,
      title: existing.title !== existing.reference ? existing.title : record.title,
      buyer: existing.buyer !== "Unknown Buyer" ? existing.buyer : record.buyer,
      province: existing.province !== "Unknown" ? existing.province : record.province,
      documents: uniqueBy([...existing.documents, ...record.documents], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      boqs: uniqueBy([...existing.boqs, ...record.boqs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      pricing_schedules: uniqueBy([...existing.pricing_schedules, ...record.pricing_schedules], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      technical_spec_files: uniqueBy([...existing.technical_spec_files, ...record.technical_spec_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      returnable_files: uniqueBy([...existing.returnable_files, ...record.returnable_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      missing_returnables: uniqueBy([...existing.missing_returnables, ...record.missing_returnables], (item) => item.toLowerCase()),
      blocker_reasons: uniqueBy([...existing.blocker_reasons, ...record.blocker_reasons], (item) => item.toLowerCase()),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      proofs: uniqueBy([...existing.proofs, ...record.proofs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      audit: [...existing.audit, ...record.audit].slice(0, 12),
      qualification_score: Math.max(existing.qualification_score, record.qualification_score),
      quote_readiness_score: Math.max(existing.quote_readiness_score, record.quote_readiness_score),
      submission_readiness_score: Math.max(existing.submission_readiness_score, record.submission_readiness_score),
      document_confidence_score: Math.max(existing.document_confidence_score || 0, record.document_confidence_score || 0),
      quote_pack_readiness_score: Math.max(existing.quote_pack_readiness_score || 0, record.quote_pack_readiness_score || 0),
      document_verification_status: existing.document_verification_status !== "pending" ? existing.document_verification_status : record.document_verification_status,
      rfq_discovered: existing.rfq_discovered || record.rfq_discovered,
      buyer_pack_downloaded: existing.buyer_pack_downloaded || record.buyer_pack_downloaded,
      buyer_pack_download_failed: existing.buyer_pack_download_failed || record.buyer_pack_download_failed,
      buyer_pack_download_timestamp: existing.buyer_pack_download_timestamp || record.buyer_pack_download_timestamp,
      buyer_pack_source: existing.buyer_pack_source || record.buyer_pack_source,
      download_failure_reason: existing.download_failure_reason || record.download_failure_reason,
      boq_detected: existing.boq_detected || record.boq_detected,
      pricing_schedule_detected: existing.pricing_schedule_detected || record.pricing_schedule_detected,
      returnables_detected: existing.returnables_detected || record.returnables_detected,
      extraction_failure_reason: existing.extraction_failure_reason || record.extraction_failure_reason,
      eligibility_failure_reason: existing.eligibility_failure_reason || record.eligibility_failure_reason,
      quote_pack_generated: existing.quote_pack_generated || record.quote_pack_generated,
      buyer_pack_status: existing.buyer_pack_status || record.buyer_pack_status,
      boq_status: existing.boq_status || record.boq_status,
      pricing_schedule_status: existing.pricing_schedule_status || record.pricing_schedule_status,
      returnables_status: existing.returnables_status || record.returnables_status,
      quote_pack_status: existing.quote_pack_status || record.quote_pack_status,
      acquisition_readiness_score: Math.max(existing.acquisition_readiness_score || 0, record.acquisition_readiness_score || 0),
      lifecycle_stage: existing.lifecycle_stage || record.lifecycle_stage,
      lifecycle_stage_label: existing.lifecycle_stage_label || record.lifecycle_stage_label,
      quote_pack_readiness_components: existing.quote_pack_readiness_components || record.quote_pack_readiness_components,
      quote_candidate_status: existing.quote_candidate_status || record.quote_candidate_status,
      pricing_review_status: existing.pricing_review_status || record.pricing_review_status,
      manual_pricing_required: existing.manual_pricing_required || record.manual_pricing_required,
      manual_pricing_required_reason: existing.manual_pricing_required_reason || record.manual_pricing_required_reason,
      pricing_action: existing.pricing_action || record.pricing_action,
      pricing_verification_status: existing.pricing_verification_status || record.pricing_verification_status,
      manual_pricing_path: existing.manual_pricing_path || record.manual_pricing_path,
      quote_pack_path: existing.quote_pack_path || record.quote_pack_path,
      proof_path: existing.proof_path || record.proof_path,
      proof_indexed: existing.proof_indexed || record.proof_indexed,
      submission_checklist_status: existing.submission_checklist_status || record.submission_checklist_status,
      manual_pricing_line_items: existing.manual_pricing_line_items || record.manual_pricing_line_items,
      manual_pricing_totals: existing.manual_pricing_totals || record.manual_pricing_totals,
      manual_pricing_validation: existing.manual_pricing_validation || record.manual_pricing_validation,
      buyer_pack_path: existing.buyer_pack_path || record.buyer_pack_path,
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => {
    const urgency = daysUntil(a.closing_date) - daysUntil(b.closing_date);
    if (Number.isFinite(urgency) && urgency !== 0) return urgency;
    return b.submission_readiness_score - a.submission_readiness_score;
  });
}

function lifecycleStageSortValue(stage) {
  const raw = safeText(stage, "").toUpperCase();
  if (raw.includes("SUBMISSION")) return 8;
  if (raw.includes("QUOTE READY")) return 7;
  if (raw.includes("QUOTE PACK GENERATED")) return 6;
  if (raw.includes("RETURNABLES")) return 5;
  if (raw.includes("PRICING")) return 4;
  if (raw.includes("BOQ")) return 3;
  if (raw.includes("DOCUMENTS CLASSIFIED")) return 2;
  if (raw.includes("BUYER PACK")) return 2;
  if (raw.includes("DISCOVER")) return 1;
  return 0;
}

function daysUntil(value) {
  if (!value) return 9999;
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return 9999;
  return Math.ceil((time - Date.now()) / 86400000);
}

function urgencyMeta(value) {
  const days = daysUntil(value);
  if (days < 0) return { label: "Overdue", tone: "red" };
  if (days <= 2) return { label: `${days}d`, tone: "red" };
  if (days <= 7) return { label: `${days}d`, tone: "amber" };
  if (days < 9999) return { label: `${days}d`, tone: "green" };
  return { label: "No date", tone: "neutral" };
}

function scoreTone(score) {
  if (score >= 80) return "green";
  if (score >= 50) return "amber";
  return "red";
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "No closing date";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No closing date");
  return date.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "2-digit" });
}

function createManualPricingLineItem(index = 1, description = "") {
  return {
    item_no: index,
    description,
    quantity: "1",
    unit: "each",
    unit_cost: "",
    markup_percent: "25",
    selling_price: "",
    vat_rate: "15",
    vat: "",
    total: "",
    supplier_source_note: "",
  };
}

function normalizeManualPricingLineItem(item, index) {
  return {
    ...createManualPricingLineItem(index, item?.description || ""),
    ...item,
    item_no: item?.item_no || item?.line_no || index,
    quantity: safeText(item?.quantity ?? item?.qty ?? "1", "1"),
    unit: safeText(item?.unit, "each"),
    unit_cost: safeText(item?.unit_cost ?? item?.cost ?? "", ""),
    markup_percent: safeText(item?.markup_percent ?? item?.markup ?? "25", "25"),
    selling_price: safeText(item?.selling_price ?? item?.selling_price_ex_vat ?? item?.unit_price ?? "", ""),
    vat_rate: safeText(item?.vat_rate ?? "15", "15"),
    vat: safeText(item?.vat ?? item?.vat_amount ?? "", ""),
    total: safeText(item?.total ?? item?.total_ex_vat ?? "", ""),
    supplier_source_note: safeText(item?.supplier_source_note ?? item?.source_note ?? item?.note ?? "", ""),
  };
}

function calculateManualPricingSummary(lineItems) {
  const normalized = asArray(lineItems).map((item, index) => normalizeManualPricingLineItem(item, index + 1));
  const summary = normalized.reduce(
    (acc, item) => {
      const quantity = normalizeNumber(item.quantity, 0);
      const unitCost = normalizeNumber(item.unit_cost, 0);
      const markupPercent = normalizeNumber(item.markup_percent, 0);
      const vatRate = normalizeNumber(item.vat_rate, 15);
      const sellingPrice = normalizeNumber(item.selling_price, unitCost > 0 ? unitCost * (1 + markupPercent / 100) : 0);
      const totalExVat = normalizeNumber(item.total, quantity * sellingPrice);
      const vatAmount = normalizeNumber(item.vat, totalExVat * vatRate / 100);
      const totalInclVat = totalExVat + vatAmount;
      const costTotal = quantity * unitCost;
      acc.subtotal_ex_vat += totalExVat;
      acc.vat_total += vatAmount;
      acc.grand_total_inc_vat += totalInclVat;
      acc.total_cost += costTotal;
      acc.line_items.push({
        ...item,
        quantity,
        unit_cost: unitCost,
        markup_percent: markupPercent,
        selling_price: sellingPrice,
        vat_rate: vatRate,
        vat: vatAmount,
        total: totalExVat,
        total_ex_vat: totalExVat,
        total_incl_vat: totalInclVat,
        unit_cost_total: costTotal,
        profit: totalExVat - costTotal,
        margin_percent: totalExVat > 0 ? ((totalExVat - costTotal) / totalExVat) * 100 : 0,
      });
      return acc;
    },
    {
      subtotal_ex_vat: 0,
      vat_total: 0,
      grand_total_inc_vat: 0,
      total_cost: 0,
      line_items: [],
    },
  );
  summary.estimated_profit = summary.subtotal_ex_vat - summary.total_cost;
  summary.margin_percent = summary.subtotal_ex_vat > 0 ? (summary.estimated_profit / summary.subtotal_ex_vat) * 100 : 0;
  summary.blockers = [];
  if (!summary.line_items.length) summary.blockers.push("No manual pricing line items entered.");
  if (summary.subtotal_ex_vat <= 0) summary.blockers.push("Pricing schedule requires a positive total.");
  if (summary.estimated_profit < 30000) summary.blockers.push("Minimum R30,000 profit not met.");
  if (summary.margin_percent < 25) summary.blockers.push("Minimum 25% margin not met.");
  summary.verified = summary.blockers.length === 0;
  return summary;
}

async function fetchEndpoint(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return { path, ok: true, data: await response.json() };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed" };
  } finally {
    clearTimeout(timeout);
  }
}

async function postEndpoint(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return { path, ok: false, error: data?.detail || data?.message || `${response.status} ${response.statusText}` };
    return { path, ok: true, data };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed" };
  } finally {
    clearTimeout(timeout);
  }
}

function ScoreChip({ label, score }) {
  return (
    <span className={`rfq-score-chip ${scoreTone(score)}`}>
      <small>{label}</small>
      <b>{score}</b>
    </span>
  );
}

function DocumentStatusChip({ label, status }) {
  return (
    <span className={`quote-status-chip ${statusTone(status)}`}>
      <small>{label}</small>
      <b>{status || "not_attempted"}</b>
    </span>
  );
}

function ArtifactList({ items, empty }) {
  if (!items.length) return <div className="rfq-empty-inline">{empty}</div>;
  return (
    <div className="rfq-artifact-list">
      {items.map((item, index) => (
        <div className="rfq-artifact" key={`${item.name}-${index}`}>
          {item.type === "BOQ" || item.type === "Pricing Schedule" ? <FileSpreadsheet size={16} /> : <FileText size={16} />}
          <div>
            <b>{item.name}</b>
            <span>{item.type}{item.status ? ` · ${item.status}` : ""}</span>
          </div>
          {item.url ? <a href={item.url.startsWith("http") ? item.url : `${API_BASE}${item.url}`} target="_blank" rel="noreferrer">Open</a> : null}
        </div>
      ))}
    </div>
  );
}

function ReturnablesChecklist({ items }) {
  if (!items.length) {
    return (
      <div className="rfq-check-row complete">
        <CheckCircle2 size={17} />
        <span>No missing returnables detected</span>
      </div>
    );
  }
  return (
    <div className="rfq-checklist">
      {items.map((item) => (
        <div className="rfq-check-row missing" key={item}>
          <ShieldAlert size={17} />
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

function LifecycleStagePill({ stage }) {
  return (
    <span className={`pill ${lifecycleTone(stage)}`}>
      {safeText(stage, "DISCOVERED")}
    </span>
  );
}

function ProductionChecklist({ rfq }) {
  const steps = [
    { label: "Discovery", passed: Boolean(rfq?.current_state || rfq?.status), detail: "RFQ loaded into the live workspace." },
    { label: "Buyer Pack", passed: Boolean(rfq?.buyer_pack_path), detail: rfq?.buyer_pack_path || "No buyer pack stored yet." },
    { label: "Documents", passed: Boolean(rfq?.documents?.length || rfq?.technical_spec_files?.length || rfq?.returnable_files?.length), detail: "Buyer docs and classifications detected." },
    { label: "Manual Pricing", passed: Boolean(rfq?.manual_pricing_path), detail: rfq?.manual_pricing_path || "No manual pricing file saved yet." },
    { label: "Pricing Verified", passed: rfq?.pricing_verification_status === "verified" || rfq?.current_state === "PRICING_VERIFIED" || rfq?.status === "Proof Captured", detail: rfq?.pricing_verification_status || "Awaiting verification." },
    { label: "Quote Pack", passed: Boolean(rfq?.quote_pack_path), detail: rfq?.quote_pack_path || "No quote pack generated yet." },
    { label: "Checklist", passed: rfq?.submission_checklist_status === "completed" || rfq?.current_state === "PROOF_CAPTURED", detail: rfq?.submission_checklist_status || "Checklist not completed yet." },
    { label: "Proof Indexed", passed: Boolean(rfq?.proof_indexed), detail: rfq?.proof_path || "No proof record indexed yet." },
  ];

  return (
    <div className="rfq-checklist">
      {steps.map((step) => (
        <div className={`rfq-check-row ${step.passed ? "complete" : "missing"}`} key={step.label}>
          {step.passed ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
          <span>
            <b>{step.label}:</b> {step.detail}
          </span>
        </div>
      ))}
    </div>
  );
}

function ManualPricingEditor({ rfq, onSaved }) {
  const applicable = rfq?.manual_pricing_required || rfq?.pricing_review_status === "REVIEW_REQUIRED_PRICING" || rfq?.pricing_review_status === "PRICING_VERIFIED";
  const [state, setState] = useState({
    loading: false,
    saving: false,
    error: "",
    message: "",
    line_items: [createManualPricingLineItem(1, rfq?.title || "Supply and delivery")],
    totals: calculateManualPricingSummary([createManualPricingLineItem(1, rfq?.title || "Supply and delivery")]),
    pricing_review_status: safeText(rfq?.pricing_review_status, ""),
    pricing_verification_status: safeText(rfq?.pricing_verification_status, ""),
    manual_pricing_path: safeText(rfq?.manual_pricing_path, ""),
    operator_note: "",
  });

  useEffect(() => {
    let cancelled = false;
    async function loadManualPricing() {
      if (!rfq?.id || !applicable) {
        setState({
          loading: false,
          saving: false,
          error: "",
          message: "",
          line_items: [createManualPricingLineItem(1, rfq?.title || "Supply and delivery")],
          totals: calculateManualPricingSummary([createManualPricingLineItem(1, rfq?.title || "Supply and delivery")]),
          pricing_review_status: safeText(rfq?.pricing_review_status, ""),
          pricing_verification_status: safeText(rfq?.pricing_verification_status, ""),
          manual_pricing_path: safeText(rfq?.manual_pricing_path, ""),
          operator_note: "",
        });
        return;
      }
      setState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
      const response = await fetchEndpoint(`/rfq-lifecycle/manual-pricing/${encodeURIComponent(rfq.id)}`);
      if (cancelled) return;
      if (response.ok && response.data?.status === "ok") {
        const manualPricing = response.data.manual_pricing || {};
        const lineItems = asArray(manualPricing.line_items).length
          ? asArray(manualPricing.line_items).map((item, index) => normalizeManualPricingLineItem(item, index + 1))
          : [createManualPricingLineItem(1, rfq?.title || "Supply and delivery")];
        setState({
          loading: false,
          saving: false,
          error: "",
          message: response.data?.saved ? "Manual pricing loaded from runtime storage." : "Enter manual pricing data to verify the RFQ.",
          line_items: lineItems,
          totals: calculateManualPricingSummary(lineItems),
          pricing_review_status: safeText(response.data?.pricing_review_status || rfq?.pricing_review_status, ""),
          pricing_verification_status: safeText(response.data?.pricing_verification_status || rfq?.pricing_verification_status, ""),
          manual_pricing_path: safeText(manualPricing.manual_pricing_path || rfq?.manual_pricing_path, ""),
          operator_note: safeText(manualPricing.operator_note, ""),
        });
      } else {
        setState({
          loading: false,
          saving: false,
          error: response.error || response.data?.message || "Manual pricing could not be loaded.",
          message: "",
          line_items: [createManualPricingLineItem(1, rfq?.title || "Supply and delivery")],
          totals: calculateManualPricingSummary([createManualPricingLineItem(1, rfq?.title || "Supply and delivery")]),
          pricing_review_status: safeText(rfq?.pricing_review_status, ""),
          pricing_verification_status: safeText(rfq?.pricing_verification_status, ""),
          manual_pricing_path: safeText(rfq?.manual_pricing_path, ""),
          operator_note: "",
        });
      }
    }
    loadManualPricing();
    return () => {
      cancelled = true;
    };
  }, [rfq?.id, applicable, rfq?.title, rfq?.manual_pricing_path, rfq?.pricing_review_status, rfq?.pricing_verification_status]);

  function updateLineItem(index, field, value) {
    setState((prev) => {
      const next = prev.line_items.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item));
      return { ...prev, line_items: next, totals: calculateManualPricingSummary(next), message: "", error: "" };
    });
  }

  function addLineItem() {
    setState((prev) => {
      const next = [...prev.line_items, createManualPricingLineItem(prev.line_items.length + 1)];
      return { ...prev, line_items: next, totals: calculateManualPricingSummary(next), message: "", error: "" };
    });
  }

  function removeLineItem(index) {
    setState((prev) => {
      const next = prev.line_items.filter((_, itemIndex) => itemIndex !== index).map((item, itemIndex) => ({ ...item, item_no: itemIndex + 1 }));
      return { ...prev, line_items: next.length ? next : [createManualPricingLineItem(1)], totals: calculateManualPricingSummary(next.length ? next : [createManualPricingLineItem(1)]), message: "", error: "" };
    });
  }

  async function saveManualPricing() {
    if (!rfq?.id) return;
    const totals = calculateManualPricingSummary(state.line_items);
    setState((prev) => ({ ...prev, saving: true, error: "", message: "" }));
    const payload = {
      line_items: totals.line_items,
      operator_note: state.operator_note,
      vat_rate: 15,
    };
    const response = await postEndpoint(`/rfq-lifecycle/manual-pricing/${encodeURIComponent(rfq.id)}`, payload);
    if (!response.ok || !response.data || (response.data.status !== "ok" && response.data.status !== "needs_review")) {
      setState((prev) => ({ ...prev, saving: false, error: response.error || response.data?.message || "Manual pricing save failed." }));
      return;
    }
    const returned = response.data || {};
    const savedLineItems = asArray(returned.line_items).length ? returned.line_items.map((item, index) => normalizeManualPricingLineItem(item, index + 1)) : totals.line_items;
    const savedTotals = returned.totals || calculateManualPricingSummary(savedLineItems);
    setState({
      loading: false,
      saving: false,
      error: returned.blockers?.length ? returned.blockers.join(" · ") : "",
      message: returned.verified ? "Manual pricing verified. Quote pack generation is now available." : "Manual pricing saved locally and remains under review.",
      line_items: savedLineItems,
      totals: { ...savedTotals, line_items: savedLineItems },
      pricing_review_status: safeText(returned.pricing_review_status || rfq?.pricing_review_status, ""),
      pricing_verification_status: safeText(returned.pricing_verification_status || rfq?.pricing_verification_status, ""),
      manual_pricing_path: safeText(returned.manual_pricing_path || rfq?.manual_pricing_path, ""),
      operator_note: state.operator_note,
    });
    onSaved?.(returned.item || returned);
  }

  if (!applicable) {
    return <div className="rfq-empty-inline">Manual pricing is only available for RFQs requiring operator pricing completion.</div>;
  }

  const totals = state.totals || calculateManualPricingSummary(state.line_items);

  return (
    <div className="rfq-tab-panel">
      <div className="rfq-detail-wide">
        <h3>Manual Pricing Entry</h3>
        <p>Enter operator pricing only. Final quote pack generation remains blocked until this data is saved and verified.</p>
      </div>
      <div className="rfq-detail-grid">
        <div className="rfq-detail-card"><span>Pricing Review</span><b>{state.pricing_review_status || "REVIEW_REQUIRED_PRICING"}</b></div>
        <div className="rfq-detail-card"><span>Verification</span><b>{state.pricing_verification_status || "needs_review"}</b></div>
        <div className="rfq-detail-card"><span>Margin</span><b>{Math.round(totals.margin_percent || 0)}%</b></div>
        <div className="rfq-detail-card"><span>Profit</span><b>{formatMoney(totals.estimated_profit || 0)}</b></div>
      </div>

      {state.loading ? <div className="rfq-empty-inline">Loading manual pricing data...</div> : null}
      {state.error ? <div className="quote-warning"><AlertTriangle size={16} />{state.error}</div> : null}
      {state.message ? <div className="quote-pricing-message">{state.message}</div> : null}

      <div className="rfq-detail-wide">
        <h4>Buyer Pack</h4>
        <p>{rfq.buyer_pack_path || "No buyer pack path available."}</p>
      </div>

      <div className="quote-pricing-table-scroll">
        <table className="quote-pricing-table">
          <thead>
            <tr>
              <th>Line</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Unit</th>
              <th>Unit Cost</th>
              <th>Markup %</th>
              <th>Selling Price</th>
              <th>VAT</th>
              <th>Total</th>
              <th>Supplier / Source Note</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {state.line_items.map((item, index) => (
              <tr key={`${item.item_no || index}-${index}`}>
                <td>{item.item_no || index + 1}</td>
                <td><input value={item.description || ""} onChange={(event) => updateLineItem(index, "description", event.target.value)} /></td>
                <td><input value={item.quantity ?? ""} onChange={(event) => updateLineItem(index, "quantity", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.unit ?? ""} onChange={(event) => updateLineItem(index, "unit", event.target.value)} /></td>
                <td><input value={item.unit_cost ?? ""} onChange={(event) => updateLineItem(index, "unit_cost", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.markup_percent ?? ""} onChange={(event) => updateLineItem(index, "markup_percent", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.selling_price ?? ""} onChange={(event) => updateLineItem(index, "selling_price", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.vat ?? ""} onChange={(event) => updateLineItem(index, "vat", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.total ?? ""} onChange={(event) => updateLineItem(index, "total", event.target.value)} inputMode="decimal" /></td>
                <td><input value={item.supplier_source_note ?? ""} onChange={(event) => updateLineItem(index, "supplier_source_note", event.target.value)} placeholder="Supplier or source note" /></td>
                <td><button type="button" onClick={() => removeLineItem(index)} disabled={state.line_items.length <= 1}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="quote-pricing-actions">
        <button type="button" disabled={state.loading || state.saving} onClick={addLineItem}>Add Line Item</button>
        <button type="button" disabled={state.loading || state.saving} onClick={saveManualPricing}>
          {state.saving ? "Saving Manual Pricing" : "Save Manual Pricing"}
        </button>
      </div>

      <div className="quote-pricing-totals">
        <div><span>Subtotal ex VAT</span><b>{formatMoney(totals.subtotal_ex_vat)}</b></div>
        <div><span>VAT Total</span><b>{formatMoney(totals.vat_total)}</b></div>
        <div><span>Grand Total inc VAT</span><b>{formatMoney(totals.grand_total_inc_vat)}</b></div>
        <div><span>Estimated Profit</span><b>{formatMoney(totals.estimated_profit)}</b></div>
        <div><span>Margin</span><b>{Math.round(totals.margin_percent || 0)}%</b></div>
      </div>

      <div className="quote-pricing-alert-grid">
        <div>
          <h4>Verification</h4>
          {totals.verified ? <p className="quote-risk">Manual pricing meets margin and profit requirements.</p> : totals.blockers.map((item) => <p className="quote-risk missing" key={item}>{item}</p>)}
        </div>
        <div>
          <h4>Buyer Pack Path</h4>
          <p>{rfq.buyer_pack_path || "No buyer pack path available."}</p>
          <h4>Technical Specs</h4>
          <ArtifactList items={rfq.technical_spec_files} empty="No technical specification files detected." />
        </div>
        <div>
          <h4>Returnables</h4>
          <ArtifactList items={rfq.returnable_files} empty="No returnable files detected." />
        </div>
      </div>
    </div>
  );
}

function DetailDrawer({ rfq, activeTab, setActiveTab, onClose, operatorState, onOperatorAction, onManualPricingSaved }) {
  if (!rfq) return null;
  const urgency = urgencyMeta(rfq.closing_date);
  const localDecision = operatorState[rfq.id];
  const [lifecycleState, setLifecycleState] = useState({ saving: false, error: "", message: "" });

  async function advanceLifecycleState(targetState) {
    if (!rfq?.id) return;
    setLifecycleState({ saving: true, error: "", message: "" });
    const response = await postEndpoint(`/rfq-lifecycle/advance/${encodeURIComponent(rfq.id)}`, {
      target_state: targetState,
      note: `manual operator advance to ${targetState}`,
    });
    if (!response.ok || !response.data) {
      setLifecycleState({ saving: false, error: response.error || "Lifecycle advance failed.", message: "" });
      return;
    }
    onManualPricingSaved?.(response.data.item || response.data);
    setLifecycleState({
      saving: false,
      error: "",
      message: `Advanced to ${safeText(response.data?.item?.current_state || targetState, targetState).replaceAll("_", " ")}`,
    });
  }

  return (
    <div className="rfq-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="rfq-drawer" aria-label="RFQ detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="rfq-drawer-head">
          <div>
            <span className="rfq-kicker">{rfq.reference}</span>
            <h2>{rfq.title}</h2>
            <p>{rfq.buyer} · {rfq.province} · {formatDate(rfq.closing_date)}</p>
          </div>
          <button className="rfq-icon-button" type="button" onClick={onClose} aria-label="Close RFQ detail">
            <X size={18} />
          </button>
        </div>

        <div className="rfq-drawer-scorebar">
          <ScoreChip label="Qual" score={rfq.qualification_score} />
          <ScoreChip label="Quote" score={rfq.quote_readiness_score} />
          <ScoreChip label="Submit" score={rfq.submission_readiness_score} />
          <span className={`rfq-urgency ${urgency.tone}`}><Clock3 size={14} />{urgency.label}</span>
        </div>

        <div className="rfq-operator-actions">
          <button type="button" onClick={() => onOperatorAction(rfq.id, "Marked for Review")}><AlertTriangle size={15} />Mark for Review</button>
          <button type="button" onClick={() => onOperatorAction(rfq.id, "On Hold")}><PauseCircle size={15} />Hold</button>
          <button type="button" onClick={() => onOperatorAction(rfq.id, "Approved for Quote Prep")}><ThumbsUp size={15} />Approve for Quote Prep</button>
          <button type="button" onClick={() => onOperatorAction(rfq.id, "Rejected Opportunity")}><Ban size={15} />Reject Opportunity</button>
        </div>
        {localDecision ? <div className="rfq-local-state">Local operator state: {localDecision}</div> : null}

        <div className="rfq-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="rfq-drawer-body">
          {activeTab === "Overview" ? (
            <div className="rfq-detail-grid">
              <div className="rfq-detail-card"><span>Status</span><b>{rfq.status}</b></div>
              <div className="rfq-detail-card"><span>Estimated Value</span><b>{formatMoney(rfq.estimated_value)}</b></div>
              <div className="rfq-detail-card"><span>Estimated Profit</span><b>{formatMoney(rfq.estimated_profit)}</b></div>
              <div className="rfq-detail-card"><span>Margin</span><b>{Math.round(rfq.margin_percent || 0)}%</b></div>
              <div className="rfq-detail-card"><span>Document Confidence</span><b>{Math.round(rfq.document_confidence_score || 0)}%</b></div>
              <div className="rfq-detail-card"><span>Document Status</span><b>{rfq.document_verification_status || "pending"}</b></div>
              <div className="rfq-detail-card"><span>Readiness</span><b>{Math.round(rfq.acquisition_readiness_score || rfq.quote_pack_readiness_score || 0)}%</b></div>
              <div className="rfq-detail-card"><span>Buyer Pack</span><b>{rfq.buyer_pack_status || "not_attempted"}</b></div>
              <div className="rfq-detail-card"><span>BOQ</span><b>{rfq.boq_status || "not_attempted"}</b></div>
              <div className="rfq-detail-card"><span>Pricing Schedule</span><b>{rfq.pricing_schedule_status || "not_attempted"}</b></div>
              <div className="rfq-detail-card"><span>Returnables</span><b>{rfq.returnables_status || "not_attempted"}</b></div>
              <div className="rfq-detail-card"><span>Quote Pack</span><b>{rfq.quote_pack_status || (rfq.quote_pack_generated ? "generated" : "not_attempted")}</b></div>
              <div className="rfq-detail-card"><span>Pricing Review</span><b>{rfq.pricing_review_status || (rfq.manual_pricing_required ? "REVIEW_REQUIRED_PRICING" : "none")}</b></div>
              <div className="rfq-detail-card"><span>Pricing Action</span><b>{rfq.pricing_action || (rfq.manual_pricing_required ? "Prepare manual pricing schedule" : "None")}</b></div>
              <div className="rfq-detail-card"><span>Quote Pack Path</span><b>{rfq.quote_pack_path ? "Stored" : "Not stored"}</b></div>
              <div className="rfq-detail-card"><span>Checklist</span><b>{rfq.submission_checklist_status || (rfq.current_state === "PROOF_CAPTURED" ? "completed" : "pending")}</b></div>
              <div className="rfq-detail-card"><span>Proof Indexed</span><b>{rfq.proof_indexed ? "Yes" : "No"}</b></div>
              <div className="rfq-detail-wide">
                <h3>Proof Path</h3>
                <p>{rfq.proof_path || "No proof record indexed."}</p>
              </div>
              <div className="rfq-detail-wide">
                <h3>Acquisition Readiness</h3>
                <div className="rfq-document-status-grid">
                  <DocumentStatusChip label="Buyer Pack" status={rfq.buyer_pack_status} />
                  <DocumentStatusChip label="BOQ" status={rfq.boq_status} />
                  <DocumentStatusChip label="Pricing" status={rfq.pricing_schedule_status} />
                  <DocumentStatusChip label="Returnables" status={rfq.returnables_status} />
                  <DocumentStatusChip label="Quote Pack" status={rfq.quote_pack_status} />
                </div>
              </div>
              <div className="rfq-detail-wide">
                <h3>Manual Production Checklist</h3>
                <ProductionChecklist rfq={rfq} />
              </div>
              <div className="rfq-detail-card"><span>Lifecycle State</span><b>{rfq.current_state || rfq.lifecycle_stage_label || rfq.lifecycle_stage || rfq.status || "Unknown"}</b></div>
              <div className="rfq-detail-wide">
                <h3>Recommended Action</h3>
                <p>{rfq.recommended_action}</p>
              </div>
              {rfq.buyer_pack_path ? (
                <div className="rfq-detail-wide">
                  <h3>Buyer Pack Path</h3>
                  <p>{rfq.buyer_pack_path}</p>
                </div>
              ) : null}
              {rfq.technical_spec_files.length ? (
                <div className="rfq-detail-wide">
                  <h3>Technical Specification Files</h3>
                  <ArtifactList items={rfq.technical_spec_files} empty="No technical spec files detected." />
                </div>
              ) : null}
              {rfq.returnable_files.length ? (
                <div className="rfq-detail-wide">
                  <h3>Returnable Files</h3>
                  <ArtifactList items={rfq.returnable_files} empty="No returnable files detected." />
                </div>
              ) : null}
              {rfq.manual_pricing_required_reason ? (
                <div className="rfq-detail-wide">
                  <h3>Pricing Requirement</h3>
                  <p>{rfq.manual_pricing_required_reason}</p>
                </div>
              ) : null}
              {rfq.eligibility_failure_reason ? (
                <div className="rfq-detail-wide">
                  <h3>Eligibility Failure</h3>
                  <p>{rfq.eligibility_failure_reason}</p>
                </div>
              ) : null}
              {rfq.extraction_failure_reason ? (
                <div className="rfq-detail-wide">
                  <h3>Extraction Failure</h3>
                  <p>{rfq.extraction_failure_reason}</p>
                </div>
              ) : null}
              {rfq.download_failure_reason ? (
                <div className="rfq-detail-wide">
                  <h3>Buyer Pack Download Failure</h3>
                  <p>{rfq.download_failure_reason}</p>
                </div>
              ) : null}
              <div className="rfq-detail-wide">
                <h3>Manual Workflow Controls</h3>
                <p>Advance the RFQ only through operator-reviewed manual states. Final submission remains locked.</p>
                {lifecycleState.error ? <div className="quote-warning"><AlertTriangle size={16} />{lifecycleState.error}</div> : null}
                {lifecycleState.message ? <div className="quote-pricing-message">{lifecycleState.message}</div> : null}
                <div className="quote-pricing-actions">
                  <button type="button" disabled={lifecycleState.saving} onClick={() => advanceLifecycleState("PRICING_VERIFIED")}>Mark Pricing Verified</button>
                  <button type="button" disabled={lifecycleState.saving} onClick={() => advanceLifecycleState("QUOTE_PACK_READY")}>Mark Quote Pack Ready</button>
                  <button type="button" disabled={lifecycleState.saving} onClick={() => advanceLifecycleState("SUBMISSION_READY_MANUAL")}>Mark Submission Ready Manual</button>
                  <button type="button" disabled={lifecycleState.saving} onClick={() => advanceLifecycleState("PROOF_CAPTURED")}>Mark Proof Captured</button>
                </div>
              </div>
              {rfq.blocker_reasons.length ? (
                <div className="rfq-detail-wide">
                  <h3>Blocker Reasons</h3>
                  {rfq.blocker_reasons.map((reason) => <p className="rfq-risk" key={reason}>{reason}</p>)}
                </div>
              ) : null}
              <div className="rfq-detail-wide">
                <h3>Risks</h3>
                {rfq.risks.length ? rfq.risks.map((risk) => <p className="rfq-risk" key={risk}>{risk}</p>) : <p>No major risks detected.</p>}
              </div>
            </div>
          ) : null}

          {activeTab === "Manual Pricing" ? (
            <ManualPricingEditor rfq={rfq} onSaved={onManualPricingSaved} />
          ) : null}
          {activeTab === "Documents" ? (
            <>
              <ArtifactList items={rfq.documents} empty="No buyer forms or source documents detected." />
              <h3 className="rfq-section-title">Technical Specs</h3>
              <ArtifactList items={rfq.technical_spec_files} empty="No technical specification files detected." />
              <h3 className="rfq-section-title">Returnables</h3>
              <ArtifactList items={rfq.returnable_files} empty="No returnable files detected." />
            </>
          ) : null}
          {activeTab === "BOQ / Pricing" ? (
            <>
              <h3 className="rfq-section-title">BOQs</h3>
              <ArtifactList items={rfq.boqs} empty="No BOQ detected." />
              <h3 className="rfq-section-title">Pricing Schedules</h3>
              <ArtifactList items={rfq.pricing_schedules} empty="No pricing schedule detected." />
            </>
          ) : null}
          {activeTab === "Qualification" ? (
            <div className="rfq-tab-panel">
              <ScoreChip label="Qualification" score={rfq.qualification_score} />
              <ReturnablesChecklist items={rfq.missing_returnables} />
            </div>
          ) : null}
          {activeTab === "Submission Readiness" ? (
            <div className="rfq-tab-panel">
              <ScoreChip label="Submission" score={rfq.submission_readiness_score} />
              <ReturnablesChecklist items={rfq.missing_returnables} />
              <p className="rfq-safety-note">Dry-run controls remain frontend read-only here. Final submit is not exposed.</p>
            </div>
          ) : null}
          {activeTab === "Proofs / Audit" ? (
            <>
              <ArtifactList items={rfq.proofs} empty="No submission proof artifacts linked to this RFQ." />
              <div className="rfq-audit-list">
                {rfq.audit.length ? rfq.audit.map((event, index) => (
                  <div key={index}>
                    <History size={15} />
                    <span>{safeText(pick(event, ["event", "message", "state", "status", "action"]), "Audit event")}</span>
                    <small>{safeText(pick(event, ["timestamp", "created_at", "time"]), "")}</small>
                  </div>
                )) : <div className="rfq-empty-inline">No audit timeline returned by the probed endpoints.</div>}
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

export default function RfqOperationsWorkspace() {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], error: "" });
  const [rfqs, setRfqs] = useState([]);
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [status, setStatus] = useState("All");
  const [readiness, setReadiness] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadRfqs() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(RFQ_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeRfqRecord(record, record._sourcePath));

      const merged = mergeRfqs(records).filter((rfq) => rfq.reference !== "RFQ" || rfq.title !== "RFQ");
      setRfqs(merged.length ? merged : DEMO_RFQS);
      setEndpointState({
        loading: false,
        results,
        error: results.some((result) => result.ok) ? "" : "No RFQ endpoints responded with usable data.",
      });
    }

    loadRfqs();
    return () => {
      cancelled = true;
    };
  }, []);

  const statuses = useMemo(() => ["All", ...uniqueBy(rfqs.map((rfq) => rfq.status), (item) => item).filter(Boolean)], [rfqs]);
  const selectedRfq = useMemo(() => rfqs.find((rfq) => rfq.id === selectedId), [rfqs, selectedId]);

  const filteredRfqs = useMemo(() => {
    const term = query.trim().toLowerCase();
    return rfqs.filter((rfq) => {
      const haystack = `${rfq.reference} ${rfq.title} ${rfq.buyer} ${rfq.source}`.toLowerCase();
      const readinessMatch =
        readiness === "All" ||
        (readiness === "Quote Ready" && lifecycleStageSortValue(rfq.lifecycle_stage_label || rfq.lifecycle_stage) >= 7) ||
        (readiness === "Submission Ready" && lifecycleStageSortValue(rfq.lifecycle_stage_label || rfq.lifecycle_stage) >= 8) ||
        (readiness === "Needs Review" && (rfq.acquisition_readiness_score < 80 || rfq.missing_returnables.length > 0)) ||
        (readiness === "High Risk" && (rfq.qualification_score < 50 || rfq.submission_readiness_score < 50)) ||
        (readiness === "Closing Soon" && daysUntil(rfq.closing_date) <= 7);
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || rfq.province === province) &&
        (status === "All" || rfq.status === status) &&
        readinessMatch
      );
    });
  }, [province, query, readiness, rfqs, status]);

  const summary = useMemo(() => ({
    total: rfqs.length,
    discovered: rfqs.filter((rfq) => rfq.rfq_discovered !== false).length,
    buyerPack: rfqs.filter((rfq) => safeText(rfq.buyer_pack_status).toLowerCase() === "downloaded").length,
    boq: rfqs.filter((rfq) => safeText(rfq.boq_status).toLowerCase() === "detected").length,
    pricing: rfqs.filter((rfq) => safeText(rfq.pricing_schedule_status).toLowerCase() === "detected").length,
    returnables: rfqs.filter((rfq) => safeText(rfq.returnables_status).toLowerCase() === "detected").length,
    quotePack: rfqs.filter((rfq) => safeText(rfq.quote_pack_status).toLowerCase() === "generated").length,
    quoteReady: rfqs.filter((rfq) => lifecycleStageSortValue(rfq.lifecycle_stage_label || rfq.lifecycle_stage) >= 7).length,
    submissionReady: rfqs.filter((rfq) => lifecycleStageSortValue(rfq.lifecycle_stage_label || rfq.lifecycle_stage) >= 8).length,
  }), [rfqs]);

  function openRfq(rfq) {
    setSelectedId(rfq.id);
    setActiveTab(rfq.manual_pricing_required || rfq.pricing_review_status === "REVIEW_REQUIRED_PRICING" ? "Manual Pricing" : "Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  function updateRfqRecord(updated) {
    const next = updated?.item || updated || {};
    const nextId = safeText(pick(next, ["id", "rfq_id", "reference", "rfq_reference"]), "");
    if (!nextId) return;
    setRfqs((prev) => prev.map((rfq) => {
      if (rfq.id !== nextId && rfq.reference !== nextId && rfq.rfq_id !== nextId) return rfq;
      return { ...rfq, ...next };
    }));
  }

  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = rfqs.some((rfq) => rfq._demo);

  return (
    <section className="rfq-ops-workspace" id="rfq-operations">
      <div className="rfq-ops-hero card">
        <div>
          <p className="eyebrow">RFQ Operations</p>
          <h1>RFQ Operations Workspace</h1>
          <p className="muted">Read-only workspace probing {API_BASE}. Operator decisions stay local unless a safe review endpoint is added later.</p>
        </div>
        <div className="rfq-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${RFQ_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="rfq-summary-grid">
        <div className="rfq-summary-card"><span>Total RFQs</span><b>{summary.total}</b></div>
        <div className="rfq-summary-card"><span>Discovered</span><b>{summary.discovered}</b></div>
        <div className="rfq-summary-card"><span>Buyer Pack</span><b>{summary.buyerPack}</b></div>
        <div className="rfq-summary-card"><span>BOQ</span><b>{summary.boq}</b></div>
        <div className="rfq-summary-card"><span>Pricing</span><b>{summary.pricing}</b></div>
        <div className="rfq-summary-card"><span>Returnables</span><b>{summary.returnables}</b></div>
        <div className="rfq-summary-card good"><span>Quote Pack</span><b>{summary.quotePack}</b></div>
        <div className="rfq-summary-card blue"><span>Quote Ready</span><b>{summary.quoteReady}</b></div>
        <div className="rfq-summary-card blue"><span>Submission Ready</span><b>{summary.submissionReady}</b></div>
      </div>

      <div className="rfq-toolbar card">
        <label className="rfq-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search RFQ, buyer, source" />
        </label>
        <label>
          <Filter size={15} />
          <select value={province} onChange={(event) => setProvince(event.target.value)}>
            {PROVINCES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <Filter size={15} />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <Filter size={15} />
          <select value={readiness} onChange={(event) => setReadiness(event.target.value)}>
            {["All", "Quote Ready", "Submission Ready", "Needs Review", "High Risk", "Closing Soon"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>

      {endpointState.error ? <div className="rfq-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="rfq-warning"><FolderOpen size={16} />No live RFQ rows were found. Showing a non-destructive workspace preview row.</div> : null}

      <div className="rfq-table-card card">
        <div className="card-head">
          <h2>RFQ Queue</h2>
          <span>{filteredRfqs.length} visible</span>
        </div>
        <div className="rfq-detail-grid rfq-funnel-grid">
          <div className="rfq-detail-card"><span>discovered_count</span><b>{summary.discovered}</b></div>
          <div className="rfq-detail-card"><span>buyer_pack_count</span><b>{summary.buyerPack}</b></div>
          <div className="rfq-detail-card"><span>boq_count</span><b>{summary.boq}</b></div>
          <div className="rfq-detail-card"><span>pricing_count</span><b>{summary.pricing}</b></div>
          <div className="rfq-detail-card"><span>returnables_count</span><b>{summary.returnables}</b></div>
          <div className="rfq-detail-card"><span>quote_pack_count</span><b>{summary.quotePack}</b></div>
          <div className="rfq-detail-card"><span>quote_ready_count</span><b>{summary.quoteReady}</b></div>
        </div>
        <div className="rfq-table-scroll">
          <table className="rfq-table">
            <thead>
              <tr>
                <th>RFQ</th>
                <th>Buyer</th>
                <th>Province</th>
                <th>Lifecycle Stage</th>
                <th>Scores</th>
                <th>Buyer Pack</th>
                <th>BOQ</th>
                <th>Pricing</th>
                <th>Returnables</th>
                <th>Quote Pack</th>
                <th>Readiness</th>
                <th>Closing</th>
                <th>Missing</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRfqs.map((rfq) => {
                const urgency = urgencyMeta(rfq.closing_date);
                return (
                  <tr key={rfq.id} onClick={() => openRfq(rfq)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openRfq(rfq)}>
                    <td>
                      <b>{rfq.reference}</b>
                      <span>{rfq.title}</span>
                    </td>
                    <td>{rfq.buyer}</td>
                    <td>{rfq.province}</td>
                    <td><LifecycleStagePill stage={operatorState[rfq.id] || rfq.lifecycle_stage_label || rfq.lifecycle_stage || rfq.status} /></td>
                    <td>
                      <div className="rfq-row-scores">
                        <ScoreChip label="Q" score={rfq.qualification_score} />
                        <ScoreChip label="P" score={rfq.acquisition_readiness_score || rfq.quote_pack_readiness_score} />
                        <ScoreChip label="S" score={rfq.submission_readiness_score} />
                      </div>
                    </td>
                    <td><DocumentStatusChip label="BP" status={rfq.buyer_pack_status} /></td>
                    <td><DocumentStatusChip label="BOQ" status={rfq.boq_status} /></td>
                    <td><DocumentStatusChip label="PR" status={rfq.pricing_schedule_status} /></td>
                    <td><DocumentStatusChip label="RET" status={rfq.returnables_status} /></td>
                    <td><DocumentStatusChip label="QP" status={rfq.quote_pack_status} /></td>
                    <td><span className="rfq-readiness-score">{Math.round(rfq.acquisition_readiness_score || rfq.quote_pack_readiness_score || 0)}%</span></td>
                    <td><span className={`rfq-urgency ${urgency.tone}`}><Clock3 size={14} />{urgency.label}</span></td>
                    <td>{rfq.missing_returnables.length}</td>
                    <td><button type="button" className="rfq-row-button" onClick={(event) => { event.stopPropagation(); openRfq(rfq); }}>Open</button></td>
                  </tr>
                );
              })}
              {!filteredRfqs.length ? (
                <tr>
                  <td colSpan="14">
                    <div className="rfq-empty-inline">No RFQs match the current filters.</div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <DetailDrawer
        rfq={selectedRfq}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
        onManualPricingSaved={updateRfqRecord}
      />
    </section>
  );
}
