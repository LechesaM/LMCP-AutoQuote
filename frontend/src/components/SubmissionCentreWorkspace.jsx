import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  FileArchive,
  FileDown,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Filter,
  Globe2,
  LockKeyhole,
  PauseCircle,
  Search,
  Save,
  ShieldAlert,
  ShieldCheck,
  ThumbsUp,
  UploadCloud,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";
import {
  BINDER_ENDPOINTS,
  DEMO_SUBMISSIONS,
  DRAWER_TABS,
  DRY_RUN_ENDPOINTS,
  OPERATOR_ACTION_ALLOWED_ROLES,
  OPERATOR_ROLE_LABELS,
  PROVINCES,
  REQUEST_TIMEOUT_MS,
  SAFETY_LOCKS,
  SUBMISSION_ENDPOINTS,
} from "./submissionCentreConfig";
import {
  submissionAuditLogPath,
  submissionAuditTrailExportPath,
  submissionAuditTrailPath,
  submissionComplianceArchiveLatestZipPath,
  submissionComplianceArchivePath,
  submissionComplianceArchiveZipPath,
  submissionComplianceArchivesPath,
  submissionEvidenceBundleExportPath,
  submissionEvidenceBundlePath,
  submissionEvidenceManifestExportPath,
  submissionEvidenceManifestPath,
  submissionEvidenceSnapshotPath,
  submissionGatePath,
  submissionGateSummaryExportPath,
  submissionGateSummaryPath,
  submissionManualCompletionExportPath,
  submissionManualCompletionPath,
  submissionPrintableReportPath,
  submissionProofExportPath,
  submissionProofPath,
  submissionReadinessChecklistExportPath,
  submissionReadinessChecklistPath,
} from "./submissionCentrePaths";

const LazySubmissionBinderReadinessPanel = lazy(() => import("./SubmissionBinderReadinessPanel"));
const LazySubmissionProofCapturePanel = lazy(() => import("./SubmissionProofCapturePanel"));
const LazySubmissionAuditTrailPanel = lazy(() => import("./SubmissionAuditTrailPanel"));
const LazySubmissionReadinessChecklistPanel = lazy(() => import("./SubmissionReadinessChecklistPanel"));
const LazySubmissionEvidenceBundlePanel = lazy(() => import("./SubmissionEvidenceBundlePanel"));
const LazySubmissionEvidenceVerificationPanel = lazy(() => import("./SubmissionEvidenceVerificationPanel"));
const LazySubmissionAccessArchivePanel = lazy(() => import("./SubmissionAccessArchivePanel"));
const LazySubmissionGateOverviewPanel = lazy(() => import("./SubmissionGateOverviewPanel"));

function safeText(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "string") return value.trim() || fallback;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
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
  const raw = safeText(value || record.submission_status || record.upload_status || record.pipeline_status || record.lifecycle_state || record.status, "Candidate");
  const lower = raw.toLowerCase();
  if (lower.includes("submit") || lower.includes("proof")) return "Submitted";
  if (lower.includes("dry") || lower.includes("upload")) return "Dry-Run Review";
  if (lower.includes("ready")) return "Ready for Review";
  if (lower.includes("hold") || lower.includes("missing")) return "On Hold";
  if (lower.includes("reject") || lower.includes("fail") || lower.includes("block")) return "Blocked";
  if (lower.includes("review")) return "Review Required";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeReadinessStatus(value, present = false) {
  const raw = safeText(value, present ? "Ready" : "Missing");
  const lower = raw.toLowerCase();
  if (lower.includes("complete") || lower.includes("ready") || lower.includes("detected") || lower.includes("ok") || lower.includes("compatible")) return "Ready";
  if (lower.includes("partial") || lower.includes("review") || lower.includes("pending") || lower.includes("dry")) return "Review";
  if (lower.includes("missing") || lower.includes("fail") || lower.includes("block") || lower.includes("incompatible")) return "Blocked";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeRuntimeUrl(value) {
  const raw = safeText(value);
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/")) return raw;
  if (raw.startsWith("runtime/")) return `/${raw}`;
  const runtimeIndex = raw.indexOf("/runtime/");
  if (runtimeIndex >= 0) return raw.slice(runtimeIndex);
  return "";
}

function normalizeArtifact(value, type = "Document") {
  if (!value) return null;
  if (typeof value === "string") {
    return { name: value.split("/").pop() || value, url: normalizeRuntimeUrl(value), type };
  }
  if (typeof value !== "object") return null;
  const url = normalizeRuntimeUrl(pick(value, ["url", "href", "path", "file_path", "local_path", "download_url", "source_url", "preview_url"]));
  const name =
    safeText(pick(value, ["name", "filename", "file_name", "title", "label", "document_name"])) ||
    (url ? url.split("/").pop() : type);
  return {
    name,
    url,
    type: safeText(pick(value, ["type", "document_type", "category"]), type),
    status: normalizeReadinessStatus(pick(value, ["status", "state", "readiness"]), true),
  };
}

function collectArtifacts(record, keys, type) {
  const direct = keys.flatMap((key) => asArray(record?.[key]));
  return uniqueBy(
    direct.map((item) => normalizeArtifact(item, type)).filter(Boolean),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function inferArtifacts(documents, pattern, type) {
  return uniqueBy(
    documents
      .filter((doc) => pattern.test(`${doc.name} ${doc.type}`))
      .map((doc) => ({ ...doc, type })),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function isSubmissionLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(rfq|tender|submission|upload|dry|proof|portal|artifact|buyer|boq|pricing|sbd|quote|closing|reference|title|description)/.test(keys);
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

    if (isSubmissionLike(value)) {
      const sig = `${sourcePath}:${safeText(pick(value, ["id", "record_id", "rfq_id", "reference", "rfq_number", "buyer_rfq_number", "title", "description"]), JSON.stringify(Object.keys(value).slice(0, 12)))}`;
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

function namedList(values) {
  return values
    .map((item) => safeText(typeof item === "object" ? pick(item, ["name", "label", "field", "document", "reason", "type"]) : item))
    .filter(Boolean);
}

function deriveRequiredArtifacts(record) {
  const explicit = namedList(asArray(pick(record, ["required_artifacts", "required_documents", "required_uploads", "returnables_required"])));
  return uniqueBy(
    explicit.length ? explicit : ["Buyer forms", "Pricing schedule", "BOQ", "Completed SBD forms", "Generated quote files"],
    (item) => item.toLowerCase(),
  );
}

function deriveFoundArtifacts(record, groups) {
  const explicit = namedList(asArray(pick(record, ["found_artifacts", "found_documents", "available_artifacts", "upload_artifacts"])));
  const inferred = [
    groups.buyer_forms.length && "Buyer forms",
    groups.pricing_schedules.length && "Pricing schedule",
    groups.boqs.length && "BOQ",
    groups.completed_sbd_forms.length && "Completed SBD forms",
    groups.generated_quote_files.length && "Generated quote files",
  ].filter(Boolean);
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase());
}

function deriveMissingArtifacts(record, required, found) {
  const explicit = namedList(asArray(pick(record, ["missing_artifacts", "missing_upload_artifacts", "missing_documents", "missing_returnables", "upload_missing", "readiness_gaps"])));
  const foundText = found.join(" ").toLowerCase();
  const inferred = required.filter((item) => !foundText.includes(item.toLowerCase().replace(/s$/, "")));
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase()).slice(0, 12);
}

function deriveScore(record, missingArtifacts, groups) {
  const explicit = pick(record, ["upload_readiness_score", "submission_readiness_score", "readiness_score", "dry_run_readiness_score"]);
  if (explicit !== undefined) return normalizeScore(explicit);
  const artifactScore = Math.min(75, (groups.buyer_forms.length + groups.pricing_schedules.length + groups.boqs.length + groups.completed_sbd_forms.length + groups.generated_quote_files.length) * 15);
  const proofScore = groups.proofs.length ? 10 : 0;
  const penalty = Math.min(50, missingArtifacts.length * 12);
  return Math.max(0, Math.min(100, artifactScore + proofScore - penalty));
}

function normalizeRisks(record, missingArtifacts, dryRunStatus, portalStatus) {
  const explicit = namedList(asArray(pick(record, ["risks", "risk_flags", "alerts", "warnings"])));
  const inferred = [];
  if (missingArtifacts.length) inferred.push(`${missingArtifacts.length} upload artifact(s) missing`);
  if (String(dryRunStatus).toLowerCase().includes("blocked")) inferred.push("Dry-run readiness blocked");
  if (String(portalStatus).toLowerCase().includes("blocked")) inferred.push("Portal compatibility blocked");
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase()).slice(0, 8);
}

function normalizeBlockers(record, risks, missingArtifacts) {
  const explicit = namedList(asArray(pick(record, ["blockers", "blocking_reasons", "hard_blockers", "production_lock_reasons"])));
  const inferred = missingArtifacts.slice(0, 5).map((item) => `${item} missing`);
  return uniqueBy([...explicit, ...inferred, ...risks.filter((risk) => /blocked|missing/i.test(risk))], (item) => item.toLowerCase()).slice(0, 10);
}

function normalizeSubmissionRecord(record, sourcePath) {
  const rfqReference = safeText(
    pick(record, ["rfq_reference", "reference", "rfq_number", "buyer_rfq_number", "bid_number", "tender_number", "id", "rfq_id", "record_id"]),
    "RFQ",
  );
  const title = safeText(pick(record, ["title", "description", "name", "opportunity_title", "tender_title", "subject"]), rfqReference);
  const buyer = safeText(pick(record, ["buyer", "buyer_name", "department", "organisation", "organization", "client", "entity"]), "Unknown Buyer");
  const province = normalizeProvince(pick(record, ["province", "buyer_province", "region", "location"]));
  const documents = uniqueBy(
    [
      ...collectArtifacts(record, ["documents", "docs", "files", "attachments", "downloaded_documents", "source_documents", "upload_artifacts"], "Document"),
      ...collectArtifacts(record, ["buyer_forms", "returnable_forms", "rfq_document", "rfq_pdf", "form", "buyer_form"], "Buyer Form"),
      ...collectArtifacts(record, ["pricing_schedules", "pricing_schedule", "price_schedule", "pricing", "price_list", "rates"], "Pricing Schedule"),
      ...collectArtifacts(record, ["boqs", "boq", "bill_of_quantities", "bill_of_quantity"], "BOQ"),
      ...collectArtifacts(record, ["completed_sbd_forms", "sbd_forms", "sbd_documents", "completed_returnables"], "Completed SBD"),
      ...collectArtifacts(record, ["generated_quote_files", "generated_files", "quote_pack_files", "submission_pack", "pack_files"], "Generated Quote File"),
      ...collectArtifacts(record, ["proofs", "submission_proofs", "proof_files", "receipts"], "Proof"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const groups = {
    buyer_forms: inferArtifacts(documents, /\b(buyer|rfq|returnable|form)\b/i, "Buyer Form"),
    pricing_schedules: inferArtifacts(documents, /\b(pric(e|ing)|schedule|rates?|quotation[-_\s]*form)\b/i, "Pricing Schedule"),
    boqs: inferArtifacts(documents, /\b(boq|bill[-_\s]*of[-_\s]*quantit)/i, "BOQ"),
    completed_sbd_forms: inferArtifacts(documents, /\b(sbd|declaration|returnable).*(complete|signed|filled|ready)?\b/i, "Completed SBD"),
    generated_quote_files: inferArtifacts(documents, /\b(quote[-_\s]*pack|generated|lmcp|submission[-_\s]*pack)\b/i, "Generated Quote File"),
    proofs: inferArtifacts(documents, /\b(proof|receipt|screenshot|confirmation)\b/i, "Proof"),
  };
  const requiredArtifacts = deriveRequiredArtifacts(record);
  const foundArtifacts = deriveFoundArtifacts(record, groups);
  const missingArtifacts = deriveMissingArtifacts(record, requiredArtifacts, foundArtifacts);
  const dryRunStatus = normalizeReadinessStatus(pick(record, ["dry_run_status", "upload_dry_run_status", "readiness_status"]), missingArtifacts.length === 0);
  const portalStatus = normalizeReadinessStatus(pick(record, ["portal_status", "portal_compatibility", "portal_health", "portal_submission_status"]), true);
  const proofStatus = normalizeReadinessStatus(pick(record, ["proof_status", "submission_proof_status"]), groups.proofs.length > 0);
  const uploadReadinessScore = deriveScore(record, missingArtifacts, groups);
  const quotePackReadinessScore = normalizeScore(pick(record, ["quote_pack_readiness_score", "quote_readiness_score", "pack_readiness_score"]), groups.generated_quote_files.length ? 82 : uploadReadinessScore);
  const risks = normalizeRisks(record, missingArtifacts, dryRunStatus, portalStatus);
  const blockers = normalizeBlockers(record, risks, missingArtifacts);
  const submissionStatus = normalizeStatus(pick(record, ["submission_status", "upload_status", "status", "lifecycle_state", "pipeline_status", "stage"]), record);
  const id = slug(pick(record, ["id", "record_id", "submission_id", "rfq_id"], "") || `${rfqReference}-${title}`) || `submission-${Math.random().toString(36).slice(2)}`;
  const recommendedNextStep =
    safeText(pick(record, ["recommended_next_step", "recommended_action", "next_action", "operator_action"])) ||
    (blockers.length ? "Hold for missing artifacts" : uploadReadinessScore >= 80 ? "Approve dry-run review" : "Mark for upload review");

  return {
    id,
    rfq_reference: rfqReference,
    title,
    buyer,
    province,
    closing_date: safeText(pick(record, ["closing_date", "closing", "close_date", "deadline", "closing_datetime"])),
    submission_status: submissionStatus,
    dry_run_status: dryRunStatus,
    portal_status: portalStatus,
    proof_status: proofStatus,
    upload_readiness_score: uploadReadinessScore,
    quote_pack_readiness_score: quotePackReadinessScore,
    required_artifacts: requiredArtifacts,
    found_artifacts: foundArtifacts,
    missing_artifacts: missingArtifacts,
    buyer_forms: groups.buyer_forms,
    pricing_schedules: groups.pricing_schedules,
    boqs: groups.boqs,
    completed_sbd_forms: groups.completed_sbd_forms,
    generated_quote_files: groups.generated_quote_files,
    proofs: groups.proofs,
    risks,
    blockers,
    recommended_next_step: recommendedNextStep,
    _sources: [sourcePath],
    _raw: record,
  };
}

function normalizeBinderFile(value, type = "Submission Binder File") {
  const artifact = normalizeArtifact(value, type);
  if (!artifact) return null;
  return {
    ...artifact,
    type: safeText(artifact.type, type),
    url: normalizeRuntimeUrl(artifact.url || pick(value, ["url", "path", "file_path", "local_path"])),
  };
}

function normalizeSubmissionBinder(record, sourcePath) {
  if (!record || typeof record !== "object") return null;
  const manifest = record.submission_binder_manifest || record.manifest || {};
  const metadata = record.metadata || {};
  let readiness = record.readiness || manifest.readiness || record.submission_binder_readiness || {};
  if (readiness && typeof readiness === "object" && readiness.readiness) readiness = readiness.readiness;
  if (!readiness || typeof readiness !== "object") readiness = {};

  const packFiles = asArray(record.files).filter((file) => /submission[_-\s]*binder|operator[_-\s]*submission/i.test(`${file?.type || ""} ${file?.name || ""}`));
  const binderFiles = uniqueBy(
    [...asArray(record.binder_files || manifest.binder_files), ...packFiles]
      .map((file) => normalizeBinderFile(file, "Submission Binder File"))
      .filter(Boolean),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const sourceFiles = uniqueBy(
    asArray(record.source_files || manifest.source_files)
      .map((file) => normalizeBinderFile(file, "Binder Source File"))
      .filter(Boolean),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );

  const packId = safeText(record.pack_id || manifest.pack_id || metadata.pack_id || record.id);
  const hasBinderShape =
    (sourcePath.includes("submission-binders") && packId) ||
    binderFiles.length ||
    record.submission_binder_score !== undefined ||
    readiness.submission_binder_score !== undefined ||
    Object.keys(manifest).length > 0;
  if (!hasBinderShape) return null;

  const score = normalizeScore(record.submission_binder_score ?? readiness.submission_binder_score ?? manifest.submission_binder_score, 0);
  const rfqReference = safeText(record.rfq_reference || manifest.rfq_reference || metadata.rfq_reference || packId, "RFQ");
  const title = safeText(record.title || manifest.title || metadata.title, rfqReference);

  return {
    pack_id: packId || slug(`${rfqReference}-${title}`),
    rfq_reference: rfqReference,
    title,
    buyer: safeText(record.buyer || manifest.buyer || metadata.buyer, "Unknown Buyer"),
    created_at: safeText(record.created_at || manifest.created_at || metadata.created_at || record.timestamp),
    submission_binder_score: score,
    pricing_completed: Boolean(record.pricing_completed ?? readiness.pricing_completed),
    formal_quote_generated: Boolean(record.formal_quote_generated ?? readiness.formal_quote_generated),
    returnables_review_completed: Boolean(record.returnables_review_completed ?? readiness.returnables_review_completed),
    missing_items: uniqueBy(namedList(asArray(record.missing_items ?? readiness.missing_items)), (item) => item.toLowerCase()),
    blockers: uniqueBy(namedList(asArray(record.blockers ?? readiness.blockers)), (item) => item.toLowerCase()),
    binder_files: binderFiles,
    source_files: sourceFiles,
    safety: record.safety || manifest.safety || {},
    _sources: [sourcePath],
  };
}

function extractSubmissionBinders(results) {
  const binders = [];
  for (const result of results) {
    if (!result.ok) continue;
    const payload = result.data;
    const candidates = [];
    if (Array.isArray(payload?.items)) {
      candidates.push(...payload.items);
    } else if (payload && typeof payload === "object") {
      candidates.push(payload);
    }
    for (const candidate of candidates) {
      const binder = normalizeSubmissionBinder(candidate, result.path);
      if (binder) binders.push(binder);
    }
  }
  return uniqueBy(binders, (binder) => binder.pack_id || `${binder.rfq_reference}:${binder.title}`.toLowerCase());
}

function tokenSet(value) {
  return slug(value)
    .split("-")
    .filter((token) => token.length >= 4 && !["rfq", "tender", "quote", "pack", "local"].includes(token));
}

function titleTokenMatch(left, right) {
  const leftTokens = tokenSet(left);
  const rightTokens = new Set(tokenSet(right));
  if (!leftTokens.length || !rightTokens.size) return false;
  const overlap = leftTokens.filter((token) => rightTokens.has(token)).length;
  return overlap >= 2 || overlap / Math.min(leftTokens.length, rightTokens.size) >= 0.45;
}

function findBinderForSubmission(submission, binders) {
  if (!binders.length) return null;
  const submissionRef = slug(submission.rfq_reference);
  const submissionTitle = slug(submission.title);
  const submissionId = slug(submission.id);

  return (
    binders.find((binder) => {
      const binderRef = slug(binder.rfq_reference);
      return binderRef && submissionRef && binderRef === submissionRef;
    }) ||
    binders.find((binder) => {
      const packId = slug(binder.pack_id);
      return packId && ((submissionRef && packId.includes(submissionRef)) || (submissionId && packId.includes(submissionId)));
    }) ||
    binders.find((binder) => titleTokenMatch(binder.title, submission.title) || (submissionTitle && slug(binder.pack_id).includes(submissionTitle.slice(0, 32)))) ||
    null
  );
}

function applyBinderImpact(submission, binder) {
  if (!binder) return submission;

  const missingReturnables = binder.missing_items.filter((item) => /returnable|sbd|company|document|form/i.test(item));
  const binderBlockers = binder.blockers.map((item) => `Binder: ${item}`);
  const binderMissing = missingReturnables.map((item) => `Binder: ${item}`);
  const baseScore = submission.upload_readiness_score;
  const boost = binder.submission_binder_score >= 85 ? 8 : 0;
  const blockerPenalty = Math.min(30, binder.blockers.length * 10 + missingReturnables.length * 6);
  const uploadReadinessScore = normalizeScore(baseScore + boost - blockerPenalty, baseScore);
  const foundArtifacts = binder.binder_files.length
    ? uniqueBy([...submission.found_artifacts, "Local submission binder"], (item) => item.toLowerCase())
    : submission.found_artifacts;
  const requiredArtifacts = uniqueBy([...submission.required_artifacts, "Local submission binder"], (item) => item.toLowerCase());
  const missingArtifacts = uniqueBy([...submission.missing_artifacts, ...binderMissing], (item) => item.toLowerCase()).slice(0, 16);
  const blockers = uniqueBy([...submission.blockers, ...binderBlockers, ...binderMissing], (item) => item.toLowerCase()).slice(0, 14);
  const risks = uniqueBy(
    [
      ...submission.risks,
      ...(binder.blockers.length ? ["Local submission binder has blockers"] : []),
      ...(binder.submission_binder_score < 85 ? ["Local submission binder below 85 readiness"] : []),
    ],
    (item) => item.toLowerCase(),
  ).slice(0, 10);

  return {
    ...submission,
    submission_binder: binder,
    upload_readiness_score: uploadReadinessScore,
    quote_pack_readiness_score: Math.max(submission.quote_pack_readiness_score, binder.submission_binder_score),
    required_artifacts: requiredArtifacts,
    found_artifacts: foundArtifacts,
    missing_artifacts: missingArtifacts,
    generated_quote_files: uniqueBy([...submission.generated_quote_files, ...binder.source_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
    blockers,
    risks,
    recommended_next_step: blockers.length ? "Review local submission binder blockers before dry-run approval" : submission.recommended_next_step,
  };
}

function attachBindersToSubmissions(submissions, binders) {
  return submissions.map((submission) => applyBinderImpact(submission, findBinderForSubmission(submission, binders)));
}

function submissionFromBinder(binder) {
  const blockers = binder.blockers.map((item) => `Binder: ${item}`);
  const missingArtifacts = binder.missing_items.map((item) => `Binder: ${item}`);
  return {
    id: slug(`binder-${binder.pack_id}`) || `binder-${Math.random().toString(36).slice(2)}`,
    rfq_reference: binder.rfq_reference || binder.pack_id || "RFQ",
    title: binder.title || "Local submission binder",
    buyer: binder.buyer || "Unknown Buyer",
    province: "Unknown",
    closing_date: "",
    submission_status: blockers.length ? "Binder Review Required" : "Binder Ready",
    dry_run_status: "Controlled Only",
    portal_status: "Not Uploaded",
    proof_status: "Pending",
    upload_readiness_score: binder.submission_binder_score,
    quote_pack_readiness_score: binder.submission_binder_score,
    required_artifacts: ["Local submission binder", "Completed pricing", "Formal quote", "Returnables review"],
    found_artifacts: binder.binder_files.length ? ["Local submission binder"] : [],
    missing_artifacts: missingArtifacts,
    buyer_forms: [],
    pricing_schedules: [],
    boqs: [],
    completed_sbd_forms: [],
    generated_quote_files: binder.source_files,
    proofs: [],
    risks: binder.submission_binder_score < 85 ? ["Local submission binder below 85 readiness"] : [],
    blockers,
    recommended_next_step: blockers.length ? "Hold submission candidate for binder fixes" : "Binder ready for Submission Centre review",
    submission_binder: binder,
    _sources: binder._sources || ["quote-compilation binder fallback"],
    _raw: binder,
  };
}

function mergeSubmissions(records) {
  const map = new Map();
  for (const record of records) {
    const key = slug(record.rfq_reference !== "RFQ" ? record.rfq_reference : record.title) || record.id;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, record);
      continue;
    }
    map.set(key, {
      ...existing,
      ...Object.fromEntries(Object.entries(record).filter(([, value]) => value !== "" && value !== 0 && value !== undefined && value !== null)),
      id: existing.id,
      rfq_reference: existing.rfq_reference !== "RFQ" ? existing.rfq_reference : record.rfq_reference,
      title: existing.title !== existing.rfq_reference ? existing.title : record.title,
      buyer: existing.buyer !== "Unknown Buyer" ? existing.buyer : record.buyer,
      province: existing.province !== "Unknown" ? existing.province : record.province,
      required_artifacts: uniqueBy([...existing.required_artifacts, ...record.required_artifacts], (item) => item.toLowerCase()),
      found_artifacts: uniqueBy([...existing.found_artifacts, ...record.found_artifacts], (item) => item.toLowerCase()),
      missing_artifacts: uniqueBy([...existing.missing_artifacts, ...record.missing_artifacts], (item) => item.toLowerCase()),
      buyer_forms: uniqueBy([...existing.buyer_forms, ...record.buyer_forms], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      pricing_schedules: uniqueBy([...existing.pricing_schedules, ...record.pricing_schedules], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      boqs: uniqueBy([...existing.boqs, ...record.boqs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      completed_sbd_forms: uniqueBy([...existing.completed_sbd_forms, ...record.completed_sbd_forms], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      generated_quote_files: uniqueBy([...existing.generated_quote_files, ...record.generated_quote_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      proofs: uniqueBy([...existing.proofs, ...record.proofs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      blockers: uniqueBy([...existing.blockers, ...record.blockers], (item) => item.toLowerCase()).slice(0, 10),
      upload_readiness_score: Math.max(existing.upload_readiness_score, record.upload_readiness_score),
      quote_pack_readiness_score: Math.max(existing.quote_pack_readiness_score, record.quote_pack_readiness_score),
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => {
    const urgency = daysUntil(a.closing_date) - daysUntil(b.closing_date);
    if (Number.isFinite(urgency) && urgency !== 0) return urgency;
    return b.upload_readiness_score - a.upload_readiness_score;
  });
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

function statusTone(status) {
  const lower = safeText(status).toLowerCase();
  if (lower.includes("ready") || lower.includes("compatible") || lower.includes("submitted") || lower.includes("verified") || lower.includes("available") || lower.includes("allowed") || lower.includes("complete") || lower.includes("ok")) return "green";
  if (lower.includes("review") || lower.includes("pending") || lower.includes("dry") || lower.includes("hold") || lower.includes("warning") || lower.includes("unknown") || lower.includes("locked")) return "amber";
  if (lower.includes("blocked") || lower.includes("missing") || lower.includes("fail") || lower.includes("reject")) return "red";
  return "neutral";
}

function formatDate(value) {
  if (!value) return "No closing date";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No closing date");
  return date.toLocaleDateString("en-ZA", { year: "numeric", month: "short", day: "2-digit" });
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function normalizeSessionRole(role) {
  const normalizedRole = safeText(role).toLowerCase();
  return OPERATOR_ROLE_LABELS[normalizedRole] ? normalizedRole : "";
}

function operatorRoleLabel(role) {
  const normalizedRole = normalizeSessionRole(role);
  return OPERATOR_ROLE_LABELS[normalizedRole] || "Unknown";
}

function operatorCan(role, action) {
  const normalizedRole = normalizeSessionRole(role);
  return (OPERATOR_ACTION_ALLOWED_ROLES[action] || []).includes(normalizedRole);
}

function operatorBlockedReason(session, action) {
  if (!session?.authenticated) return "Login required. Operator session is missing or expired.";
  const role = normalizeSessionRole(session?.operator?.role);
  if (!role) return "Authenticated operator role is not recognized.";
  if (operatorCan(role, action)) return "";
  if (action.startsWith("proof_")) return `${operatorRoleLabel(role)} role cannot access manual submission proof actions.`;
  if (action.startsWith("archive_")) return `${operatorRoleLabel(role)} role cannot manage compliance archives.`;
  return `${operatorRoleLabel(role)} role cannot use this action.`;
}

async function fetchEndpoint(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      signal: controller.signal,
      credentials: options.credentials || "include",
      headers: options.headers || {},
    });
    if (!response.ok) {
      let error = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        error = safeText(payload?.detail, error) || error;
      } catch {
        try {
          const text = await response.text();
          if (text) error = text;
        } catch {
          // ignore body parsing failure
        }
      }
      const failure = new Error(error);
      failure.status = response.status;
      throw failure;
    }
    return { path, ok: true, data: await response.json() };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed", status: error.status || 0 };
  } finally {
    clearTimeout(timeout);
  }
}

async function postEndpoint(path, body, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal: controller.signal,
      credentials: options.credentials || "include",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      body: JSON.stringify(body ?? {}),
    });
    if (!response.ok) {
      let error = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        error = safeText(payload?.detail, error) || error;
      } catch {
        try {
          const text = await response.text();
          if (text) error = text;
        } catch {
          // ignore body parsing failure
        }
      }
      return { path, ok: false, error, status: response.status };
    }
    return { path, ok: true, data: await response.json() };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed", status: error.status || 0 };
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchTextEndpoint(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      signal: controller.signal,
      credentials: options.credentials || "include",
      headers: options.headers || {},
    });
    if (!response.ok) {
      const failure = new Error(`${response.status} ${response.statusText}`);
      failure.status = response.status;
      throw failure;
    }
    return { path, ok: true, data: await response.text() };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed", status: error.status || 0 };
  } finally {
    clearTimeout(timeout);
  }
}

async function downloadEndpoint(path, fallbackFilename, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      signal: controller.signal,
      credentials: options.credentials || "include",
      headers: options.headers || {},
    });
    if (!response.ok) {
      let error = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        error = safeText(payload?.detail, error) || error;
      } catch {
        try {
          const text = await response.text();
          if (text) error = text;
        } catch {
          // ignore body parsing failure
        }
      }
      const failure = new Error(error);
      failure.status = response.status;
      throw failure;
    }
    const blob = await response.blob();
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = fallbackFilename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(href);
    return { path, ok: true };
  } catch (error) {
    return { path, ok: false, error: error.message || "request failed", status: error.status || 0 };
  } finally {
    clearTimeout(timeout);
  }
}

function manualCompletionFormFromRecord(record) {
  return {
    submitted_by: safeText(record?.submitted_by),
    submitted_at: safeText(record?.submitted_at),
    portal_name: safeText(record?.portal_name),
    portal_reference: safeText(record?.portal_reference),
    notes: safeText(record?.notes),
    uploaded_file_names: asArray(record?.uploaded_file_names).map((item) => safeText(item)).filter(Boolean).join("\n"),
  };
}

function submissionProofFormFromRecord(record) {
  return {
    submitted_by: safeText(record?.submitted_by),
    submission_timestamp: safeText(record?.submission_timestamp),
    portal_name: safeText(record?.portal_name),
    portal_reference: safeText(record?.portal_reference),
    proof_notes: safeText(record?.proof_notes),
    buyer_reference: safeText(record?.buyer_reference),
    uploaded_files: asArray(record?.uploaded_files).map((item) => safeText(item)).filter(Boolean).join("\n"),
    screenshot_paths: asArray(record?.screenshot_paths).map((item) => safeText(item)).filter(Boolean).join("\n"),
    confirmation_message: safeText(record?.confirmation_message),
    screenshot_notes: safeText(record?.screenshot_notes),
    email_proof: safeText(record?.email_proof),
    portal_proof: safeText(record?.portal_proof),
    receipt_reference: safeText(record?.receipt_reference),
    proof_reference: safeText(record?.proof_reference),
  };
}

function ScoreChip({ label, score }) {
  return (
    <span className={`submission-score-chip ${scoreTone(score)}`}>
      <small>{label}</small>
      <b>{score}</b>
    </span>
  );
}

function parsePrintableReportPreview(html) {
  if (!html) {
    return {
      generated_at: "",
      status: "unknown",
      final_submit_locked: true,
      automated_submit_disabled: true,
      audit_event_count: 0,
      audit_warning_count: 0,
      evidence_snapshot_verification_status: "unknown",
      evidence_snapshot_hash: "",
      evidence_snapshot_generated_at: "",
      submission_proof_status: "unknown",
      submission_proof_hash: "",
      submission_proof_saved_at: "",
    };
  }
  try {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const meta = (name) => safeText(doc.querySelector(`meta[name="${name}"]`)?.getAttribute("content"));
    return {
      generated_at: meta("lmcp-report-generated-at"),
      status: meta("lmcp-report-status") || "unknown",
      final_submit_locked: meta("lmcp-report-final-submit-locked") !== "false",
      automated_submit_disabled: meta("lmcp-report-automated-submit-disabled") !== "false",
      audit_event_count: normalizeNumber(meta("lmcp-report-audit-event-count"), 0),
      audit_warning_count: normalizeNumber(meta("lmcp-report-audit-warning-count"), 0),
      evidence_snapshot_verification_status: meta("lmcp-report-snapshot-status") || "unknown",
      evidence_snapshot_hash: meta("lmcp-report-snapshot-hash"),
      evidence_snapshot_generated_at: meta("lmcp-report-snapshot-generated-at"),
      submission_proof_status: meta("lmcp-report-proof-status") || "unknown",
      submission_proof_hash: meta("lmcp-report-proof-hash"),
      submission_proof_saved_at: meta("lmcp-report-proof-saved-at"),
    };
  } catch {
    return {
      generated_at: "",
      status: "unknown",
      final_submit_locked: true,
      automated_submit_disabled: true,
      audit_event_count: 0,
      audit_warning_count: 0,
      evidence_snapshot_verification_status: "unknown",
      evidence_snapshot_hash: "",
      evidence_snapshot_generated_at: "",
      submission_proof_status: "unknown",
      submission_proof_hash: "",
      submission_proof_saved_at: "",
    };
  }
}

function SubmissionGateCard({
  authState,
  authForm,
  onAuthFormChange,
  onAuthLogin,
  onAuthLogout,
  onAuthBootstrap,
  gateState,
  summaryState,
  checklistState,
  auditState,
  auditTrailState,
  readinessChecklistState,
  evidenceState,
  evidenceBundleState,
  submissionPrintableReportState,
  submissionEvidenceSnapshotState,
  submissionComplianceArchiveState,
  submissionProofState,
  submissionProofForm,
  onSubmissionProofChange,
  onSubmissionProofSave,
  onSubmissionProofRequest,
  onSubmissionProofDownload,
  manualCompletionState,
  manualCompletionForm,
  onManualCompletionChange,
  onManualCompletionSave,
  onPrintableReportRequest,
  packId,
  onSummaryRequest,
  onChecklistRequest,
  onAuditRequest,
  onAuditTrailRequest,
  onReadinessChecklistRequest,
  onEvidenceRequest,
  onEvidenceBundleRequest,
  onEvidenceSnapshotRequest,
  onComplianceArchiveCreateRequest,
  onComplianceArchivesRequest,
  onComplianceArchiveDownload,
}) {
  const gate = gateState.data;
  const summary = summaryState.data;
  const checklist = checklistState.data;
  const audit = auditState.data;
  const auditTrail = auditTrailState.data;
  const readinessChecklist = readinessChecklistState.data;
  const evidence = evidenceState.data;
  const evidenceBundle = evidenceBundleState.data;
  const manualCompletion = manualCompletionState.data?.manual_completion || (manualCompletionState.data?.status === "ok" ? manualCompletionState.data : null);
  const manualCompletionGate = gate?.manual_completion && typeof gate.manual_completion === "object" ? gate.manual_completion : {};
  const manualCompletionAllowed = manualCompletionGate.allowed === true;
  const finalSubmitBlockerMessage = manualCompletionAllowed
    ? "Final submission remains locked in this workspace."
    : safeText(manualCompletionGate.blocked_reason, "Final submission is blocked until a valid manual completion record has been saved.");
  const safetyFlags = gate?.safety_flags && typeof gate.safety_flags === "object" ? Object.entries(gate.safety_flags) : [];
  const evidenceSafetyFlags = evidence?.safety_flags && typeof evidence.safety_flags === "object" ? Object.entries(evidence.safety_flags) : safetyFlags;
  const manualDownloadUrl = packId && manualCompletion ? `${API_BASE}${submissionManualCompletionExportPath(packId)}` : "";
  const auditEvents = asArray(audit?.events);
  const auditTrailEvents = asArray(auditTrail?.events);
  const evidenceFiles = asArray(evidence?.evidence_files);
  const evidenceBlockers = asArray(evidence?.blockers);
  const evidenceMissingReturnables = asArray(evidence?.missing_returnables);
  const auditReference = gate?.rfq_reference || audit?.rfq_reference || checklist?.rfq_reference;
  const auditTrailJsonDownloadUrl = packId ? `${API_BASE}${submissionAuditTrailExportPath(packId)}` : "";
  const readinessChecklistJsonDownloadUrl = packId ? `${API_BASE}${submissionReadinessChecklistExportPath(packId, gate?.rfq_reference || readinessChecklist?.rfq_reference)}` : "";
  const evidenceBundleJsonDownloadUrl = packId ? `${API_BASE}${submissionEvidenceBundleExportPath(packId, gate?.rfq_reference || readinessChecklist?.rfq_reference || "")}` : "";
  const evidenceReference = gate?.rfq_reference || evidence?.rfq_reference || auditReference;
  const evidenceManifestDownloadUrl = packId ? `${API_BASE}${submissionEvidenceManifestExportPath(packId, evidenceReference)}` : "";
  const summaryReference = summary?.rfq_reference || gate?.rfq_reference || evidenceReference;
  const summaryDownloadUrl = packId ? `${API_BASE}${submissionGateSummaryExportPath(packId, summaryReference)}` : "";

  function auditTrailEventSummary(event) {
    const payload = event && typeof event.payload === "object" && !Array.isArray(event.payload) ? event.payload : {};
    const parts = [];
    if (safeText(payload.reason_code)) parts.push(safeText(payload.reason_code, "").replaceAll("_", " "));
    if (Object.prototype.hasOwnProperty.call(payload, "allowed")) parts.push(payload.allowed ? "allowed" : "blocked");
    if (safeText(payload.blocked_reason)) parts.push(safeText(payload.blocked_reason, 180));
    if (safeText(payload.status)) parts.push(`status: ${safeText(payload.status, 40)}`);
    if (Object.prototype.hasOwnProperty.call(payload, "warning_count")) parts.push(`warnings: ${safeText(payload.warning_count)}`);
    if (Object.prototype.hasOwnProperty.call(payload, "count")) parts.push(`count: ${safeText(payload.count)}`);
    if (Object.prototype.hasOwnProperty.call(payload, "uploaded_file_count")) parts.push(`files: ${safeText(payload.uploaded_file_count)}`);
    return parts.length ? parts.join(" · ") : "Audit event recorded locally.";
  }

  return (
    <div className="submission-gate-card card">
      <div className="submission-gate-head">
          <div>
            <p className="eyebrow">Submission Gate</p>
            <h2>Read-Only Binder Gate</h2>
            <p className="muted">Final submission is blocked by design. Manual upload only.</p>
          </div>
        <button type="button" disabled>
          <Ban size={15} />
          Final Submit Locked
        </button>
      </div>

      {!packId ? (
        <div className="submission-gate-empty">Select a submission with a local binder to evaluate the gate.</div>
      ) : gateState.loading ? (
        <div className="submission-gate-empty">Checking local binder gate...</div>
      ) : gateState.error ? (
        <div className="submission-gate-warning"><AlertTriangle size={15} />{gateState.error}</div>
      ) : gate ? (
        <>
          <Suspense fallback={<div className="submission-gate-manual-card"><div className="submission-gate-empty">Loading gate overview...</div></div>}>
            <LazySubmissionGateOverviewPanel
              packId={packId}
              gate={gate}
              summaryState={summaryState}
              summary={summary}
              summaryDownloadUrl={summaryDownloadUrl}
              onSummaryRequest={onSummaryRequest}
              manualCompletionAllowed={manualCompletionAllowed}
              finalSubmitBlockerMessage={finalSubmitBlockerMessage}
              manualCompletionState={manualCompletionState}
              manualCompletionForm={manualCompletionForm}
              manualCompletion={manualCompletion}
              manualDownloadUrl={manualDownloadUrl}
              onManualCompletionSave={onManualCompletionSave}
              onManualCompletionChange={onManualCompletionChange}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-audit-trail-card"><div className="submission-gate-empty">Loading audit trail panel...</div></div>}>
            <LazySubmissionAuditTrailPanel
              packId={packId}
              auditTrailState={auditTrailState}
              auditTrailJsonDownloadUrl={auditTrailJsonDownloadUrl}
              onAuditTrailRequest={onAuditTrailRequest}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-readiness-card"><div className="submission-gate-empty">Loading readiness checklist panel...</div></div>}>
            <LazySubmissionReadinessChecklistPanel
              packId={packId}
              readinessChecklistState={readinessChecklistState}
              readinessChecklistJsonDownloadUrl={readinessChecklistJsonDownloadUrl}
              onReadinessChecklistRequest={onReadinessChecklistRequest}
              readinessChecklist={readinessChecklist}
              readinessFinalLabel={readinessFinalLabel}
              readinessFinalStatus={readinessFinalStatus}
              readinessManualStatus={readinessManualStatus}
              readinessAuditCount={readinessAuditCount}
              readinessAuditWarningCount={readinessAuditWarningCount}
              readinessLatestAuditSummary={readinessLatestAuditSummary}
              readinessBlockers={readinessBlockers}
              readinessWarnings={readinessWarnings}
              manualSubmissionChecklist={manualSubmissionChecklist}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-bundle-card"><div className="submission-gate-empty">Loading evidence bundle panel...</div></div>}>
            <LazySubmissionEvidenceBundlePanel
              packId={packId}
              evidenceBundleState={evidenceBundleState}
              evidenceBundleJsonDownloadUrl={evidenceBundleJsonDownloadUrl}
              onEvidenceBundleRequest={onEvidenceBundleRequest}
              evidenceBundle={evidenceBundle}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-verification-stack"><div className="submission-gate-empty">Loading evidence verification panels...</div></div>}>
            <LazySubmissionEvidenceVerificationPanel
              packId={packId}
              submissionPrintableReportState={submissionPrintableReportState}
              submissionEvidenceSnapshotState={submissionEvidenceSnapshotState}
              onPrintableReportRequest={onPrintableReportRequest}
              onEvidenceSnapshotRequest={onEvidenceSnapshotRequest}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-archive-card"><div className="submission-gate-empty">Loading access and archive panels...</div></div>}>
            <LazySubmissionAccessArchivePanel
              packId={packId}
              authForm={authForm}
              authState={authState}
              onAuthFormChange={onAuthFormChange}
              onAuthLogin={onAuthLogin}
              onAuthBootstrap={onAuthBootstrap}
              onAuthLogout={onAuthLogout}
              submissionComplianceArchiveState={submissionComplianceArchiveState}
              onComplianceArchiveCreateRequest={onComplianceArchiveCreateRequest}
              onComplianceArchivesRequest={onComplianceArchivesRequest}
              onComplianceArchiveDownload={onComplianceArchiveDownload}
            />
          </Suspense>
          <Suspense fallback={<div className="submission-gate-proof-card"><div className="submission-gate-empty">Loading proof capture panel...</div></div>}>
            <LazySubmissionProofCapturePanel
              packId={packId}
              authState={authState}
              submissionProofState={submissionProofState}
              submissionProofForm={submissionProofForm}
              onSubmissionProofChange={onSubmissionProofChange}
              onSubmissionProofSave={onSubmissionProofSave}
              onSubmissionProofRequest={onSubmissionProofRequest}
              onSubmissionProofDownload={onSubmissionProofDownload}
            />
          </Suspense>
      </>
    ) : (
      <div className="submission-gate-empty">No gate data available. Final submission remains locked.</div>
    )}
  </div>
  );
}

function StatusChip({ label, status }) {
  return (
    <span className={`submission-status-chip ${statusTone(status)}`}>
      <small>{label}</small>
      <b>{status}</b>
    </span>
  );
}

function ArtifactList({ items, empty }) {
  if (!items.length) return <div className="submission-empty-inline">{empty}</div>;
  return (
    <div className="submission-artifact-list">
      {items.map((item, index) => (
        <div className="submission-artifact" key={`${item.type}-${item.name}-${index}`}>
          {item.type === "BOQ" || item.type === "Pricing Schedule" ? <FileSpreadsheet size={16} /> : item.type === "Proof" ? <FileCheck2 size={16} /> : item.type === "Generated Quote File" ? <FileArchive size={16} /> : <FileText size={16} />}
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

function ArtifactChecklist({ required, found, missing }) {
  const foundText = found.join(" ").toLowerCase();
  return (
    <div className="submission-checklist">
      {required.map((item, index) => {
        const isMissing = missing.some((missingItem) => missingItem.toLowerCase().includes(item.toLowerCase().replace(/s$/, "")));
        const isFound = !isMissing && foundText.includes(item.toLowerCase().replace(/s$/, ""));
        return (
          <div className={`submission-check-row ${isFound ? "complete" : isMissing ? "missing" : "review"}`} key={`${item}-${index}`}>
            {isFound ? <CheckCircle2 size={17} /> : <ShieldAlert size={17} />}
            <span>{item}</span>
            <b>{isFound ? "Found" : isMissing ? "Missing" : "Review"}</b>
          </div>
        );
      })}
    </div>
  );
}

function SafetyBanner() {
  return (
    <div className="submission-safety-banner card">
      <div>
        <p className="eyebrow">Submission Safety</p>
        <h2>Controlled Dry-Run Workspace</h2>
        <p className="muted">This frontend view does not expose email sending, portal upload, or final submit actions.</p>
      </div>
      <div className="submission-lock-grid">
        {SAFETY_LOCKS.map((lock) => (
          <span key={lock}>
            <LockKeyhole size={15} />
            {lock}
          </span>
        ))}
      </div>
    </div>
  );
}

function BinderSafetyLabels() {
  return (
    <div className="submission-binder-labels">
      {BINDER_SAFETY_LABELS.map((label) => (
        <span key={label}>
          <LockKeyhole size={13} />
          {label}
        </span>
      ))}
    </div>
  );
}

function BinderReadinessFlags({ binder }) {
  return (
    <div className="submission-binder-flags">
      <div className={binder.pricing_completed ? "complete" : "review"}><span>Pricing</span><b>{binder.pricing_completed ? "Complete" : "Review"}</b></div>
      <div className={binder.formal_quote_generated ? "complete" : "review"}><span>Formal Quote</span><b>{binder.formal_quote_generated ? "Generated" : "Missing"}</b></div>
      <div className={binder.returnables_review_completed ? "complete" : "review"}><span>Returnables</span><b>{binder.returnables_review_completed ? "Reviewed" : "Review"}</b></div>
    </div>
  );
}

function BinderOperatorControls({ binder, operatorState, onOperatorAction }) {
  if (!binder) return null;
  const stateKey = `binder:${binder.pack_id}`;
  const localDecision = operatorState[stateKey];
  return (
    <>
      <div className="submission-binder-actions">
        <button type="button" onClick={() => onOperatorAction(stateKey, "Binder Accepted for Review")}><ShieldCheck size={15} />Binder Accepted for Review</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Needs Binder Fix")}><ShieldAlert size={15} />Needs Binder Fix</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Needs Returnables Fix")}><FileCheck2 size={15} />Needs Returnables Fix</button>
        <button type="button" onClick={() => onOperatorAction(stateKey, "Hold Submission Candidate")}><PauseCircle size={15} />Hold Submission Candidate</button>
      </div>
      {localDecision ? <div className="submission-local-state">Local binder state: {localDecision}</div> : null}
    </>
  );
}

function SubmissionBinderDetail({ binder, operatorState, onOperatorAction }) {
  if (!binder) {
    return (
      <div className="submission-binder-empty">
        <BinderSafetyLabels />
        <p>No local submission binder is linked to this RFQ yet.</p>
      </div>
    );
  }

  return (
    <div className="submission-binder-detail">
      <BinderSafetyLabels />
      <div className="submission-binder-headline">
        <div>
          <span className="submission-kicker">{binder.pack_id}</span>
          <h3>{binder.rfq_reference}</h3>
          <p>{binder.title} · {binder.buyer}</p>
        </div>
        <ScoreChip label="Binder" score={binder.submission_binder_score} />
      </div>
      <BinderReadinessFlags binder={binder} />
      <BinderOperatorControls binder={binder} operatorState={operatorState} onOperatorAction={onOperatorAction} />

      <h3 className="submission-section-title">Missing Items</h3>
      <div className="submission-risk-list">
        {(binder.missing_items.length ? binder.missing_items : ["No binder missing items detected."]).map((item, index) => <p className="submission-risk blocker" key={`binder-missing-${item}-${index}`}>{item}</p>)}
      </div>

      <h3 className="submission-section-title">Blockers</h3>
      <div className="submission-risk-list">
        {(binder.blockers.length ? binder.blockers : ["No binder blockers detected."]).map((item, index) => <p className="submission-risk blocker" key={`binder-blocker-${item}-${index}`}>{item}</p>)}
      </div>

      <h3 className="submission-section-title">Binder Files</h3>
      <ArtifactList items={binder.binder_files} empty="No generated binder files detected." />
      <h3 className="submission-section-title">Source Files</h3>
      <ArtifactList items={binder.source_files} empty="No binder source files detected." />
    </div>
  );
}

function SubmissionBinderReadinessSection({ binders, focusedBinder, operatorState, onOperatorAction }) {
  const binder = focusedBinder || binders[0];
  const readyCount = binders.filter((item) => item.submission_binder_score >= 85 && !item.blockers.length).length;
  const blockerCount = binders.filter((item) => item.blockers.length > 0).length;

  return (
    <div className="submission-binder-section card">
      <div className="submission-binder-section-head">
        <div>
          <p className="eyebrow">Submission Binder Readiness</p>
          <h2>Local Binder Review</h2>
          <p className="muted">Read-only integration from local quote compilation packs. No upload, email, or final submit action is exposed.</p>
        </div>
        <BinderSafetyLabels />
      </div>

      {!binders.length ? (
        <div className="submission-binder-empty">
          <p>No local submission binders were found under runtime/quote_compilation.</p>
        </div>
      ) : (
        <>
          <div className="submission-binder-summary">
            <div><span>Binders</span><b>{binders.length}</b></div>
            <div><span>Ready &gt;=85</span><b>{readyCount}</b></div>
            <div><span>With Blockers</span><b>{blockerCount}</b></div>
            <div><span>Focused Score</span><b>{binder?.submission_binder_score ?? 0}</b></div>
          </div>

          {binder ? (
            <div className="submission-binder-focus">
              <div className="submission-binder-headline">
                <div>
                  <span className="submission-kicker">{binder.rfq_reference}</span>
                  <h3>{binder.title}</h3>
                  <p>{binder.buyer} · {formatDate(binder.created_at)}</p>
                </div>
                <ScoreChip label="Binder" score={binder.submission_binder_score} />
              </div>
              <BinderReadinessFlags binder={binder} />
              <BinderOperatorControls binder={binder} operatorState={operatorState} onOperatorAction={onOperatorAction} />
              <div className="submission-binder-columns">
                <div>
                  <h3 className="submission-section-title">Missing Items</h3>
                  <div className="submission-risk-list">
                    {(binder.missing_items.length ? binder.missing_items : ["No binder missing items detected."]).map((item, index) => <p className="submission-risk blocker" key={`focus-missing-${item}-${index}`}>{item}</p>)}
                  </div>
                </div>
                <div>
                  <h3 className="submission-section-title">Binder Files</h3>
                  <ArtifactList items={binder.binder_files} empty="No generated binder files detected." />
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function DetailDrawer({ submission, activeTab, setActiveTab, onClose, operatorState, onOperatorAction }) {
  if (!submission) return null;
  const urgency = urgencyMeta(submission.closing_date);
  const localDecision = operatorState[submission.id];

  return (
    <div className="submission-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="submission-drawer" aria-label="Submission detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="submission-drawer-head">
          <div>
            <span className="submission-kicker">{submission.rfq_reference}</span>
            <h2>{submission.title}</h2>
            <p>{submission.buyer} · {submission.province} · {formatDate(submission.closing_date)}</p>
          </div>
          <button className="submission-icon-button" type="button" onClick={onClose} aria-label="Close submission detail">
            <X size={18} />
          </button>
        </div>

        <div className="submission-drawer-scorebar">
          <ScoreChip label="Upload" score={submission.upload_readiness_score} />
          <ScoreChip label="Quote Pack" score={submission.quote_pack_readiness_score} />
          {submission.submission_binder ? <ScoreChip label="Binder" score={submission.submission_binder.submission_binder_score} /> : null}
          <StatusChip label="Dry-Run" status={submission.dry_run_status} />
          <span className={`submission-urgency ${urgency.tone}`}><Clock3 size={14} />{urgency.label}</span>
        </div>

        <div className="submission-operator-actions">
          <button type="button" onClick={() => onOperatorAction(submission.id, "Marked for Upload Review")}><UploadCloud size={15} />Mark for Upload Review</button>
          <button type="button" onClick={() => onOperatorAction(submission.id, "Held for Missing Artifacts")}><PauseCircle size={15} />Hold for Missing Artifacts</button>
          <button type="button" onClick={() => onOperatorAction(submission.id, "Approved Dry-Run Review")}><ThumbsUp size={15} />Approve Dry-Run Review</button>
          <button type="button" onClick={() => onOperatorAction(submission.id, "Rejected Submission Candidate")}><Ban size={15} />Reject Submission Candidate</button>
        </div>
        {localDecision ? <div className="submission-local-state">Local operator state: {localDecision}</div> : null}

        <div className="submission-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="submission-drawer-body">
          {activeTab === "Overview" ? (
            <div className="submission-detail-grid">
              <div className="submission-detail-card"><span>Submission</span><b>{submission.submission_status}</b></div>
              <div className="submission-detail-card"><span>Dry-Run</span><b>{submission.dry_run_status}</b></div>
              <div className="submission-detail-card"><span>Portal</span><b>{submission.portal_status}</b></div>
              <div className="submission-detail-card"><span>Proof</span><b>{submission.proof_status}</b></div>
              <div className="submission-detail-wide">
                <h3>Recommended Next Step</h3>
                <p>{submission.recommended_next_step}</p>
              </div>
            </div>
          ) : null}

          {activeTab === "Upload Artifacts" ? <ArtifactChecklist required={submission.required_artifacts} found={submission.found_artifacts} missing={submission.missing_artifacts} /> : null}
          {activeTab === "Buyer Forms" ? <ArtifactList items={submission.buyer_forms} empty="No buyer forms detected." /> : null}
          {activeTab === "BOQ / Pricing" ? (
            <>
              <h3 className="submission-section-title">BOQs</h3>
              <ArtifactList items={submission.boqs} empty="No BOQ detected." />
              <h3 className="submission-section-title">Pricing Schedules</h3>
              <ArtifactList items={submission.pricing_schedules} empty="No pricing schedule detected." />
              <h3 className="submission-section-title">Completed SBD Forms</h3>
              <ArtifactList items={submission.completed_sbd_forms} empty="No completed SBD forms detected." />
            </>
          ) : null}
          {activeTab === "Proofs" ? (
            <>
              <StatusChip label="Proof" status={submission.proof_status} />
              <ArtifactList items={submission.proofs} empty="No proof artifacts linked to this RFQ." />
              <ArtifactList items={submission.generated_quote_files} empty="No generated quote files detected." />
            </>
          ) : null}
          {activeTab === "Portal" ? (
            <div className="submission-detail-grid">
              <div className="submission-detail-card"><span>Portal Status</span><b>{submission.portal_status}</b></div>
              <div className="submission-detail-card"><span>Dry-Run Status</span><b>{submission.dry_run_status}</b></div>
              <div className="submission-detail-wide"><h3>Safety Locks</h3><p>{SAFETY_LOCKS.join(" · ")}</p></div>
            </div>
          ) : null}
          {activeTab === "Submission Binder" ? (
            <SubmissionBinderDetail binder={submission.submission_binder} operatorState={operatorState} onOperatorAction={onOperatorAction} />
          ) : null}
          {activeTab === "Risks / Blockers" ? (
            <div className="submission-risk-list">
              {(submission.blockers.length ? submission.blockers : ["No hard blockers detected."]).map((blocker, index) => <p className="submission-risk blocker" key={`blocker-${blocker}-${index}`}>{blocker}</p>)}
              {submission.risks.map((risk, index) => <p className="submission-risk" key={`risk-${risk}-${index}`}>{risk}</p>)}
            </div>
          ) : null}

          <p className="submission-safety-note">Local review state only. This workspace cannot send email, upload to a portal, or perform final submit.</p>
        </div>
      </aside>
    </div>
  );
}

function PanelShell({ title, icon: Icon, children }) {
  return (
    <div className="submission-panel card">
      <div className="submission-panel-head">
        <h3>{Icon ? <Icon size={16} /> : null}{title}</h3>
      </div>
      {children}
    </div>
  );
}

export default function SubmissionCentreWorkspace({
  authState,
  onRefreshAuth,
  onLogin,
  onLogout,
  onBootstrapAdmin,
}) {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], dryRunResults: [], binderResults: [], error: "" });
  const [submissions, setSubmissions] = useState([]);
  const [submissionBinders, setSubmissionBinders] = useState([]);
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [submissionStatus, setSubmissionStatus] = useState("All");
  const [dryRunStatus, setDryRunStatus] = useState("All");
  const [readiness, setReadiness] = useState("All");
  const [blockersOnly, setBlockersOnly] = useState(false);
  const [urgency, setUrgency] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});
  const [authForm, setAuthForm] = useState({
    operator_id: "",
    password: "",
    bootstrap_operator_id: "",
    bootstrap_display_name: "",
    bootstrap_password: "",
  });
  const [submissionGateState, setSubmissionGateState] = useState({ loading: false, data: null, error: "" });
  const [submissionGateSummaryState, setSubmissionGateSummaryState] = useState({ loading: false, data: null, error: "" });
  const [submissionChecklistState, setSubmissionChecklistState] = useState({ loading: false, data: null, error: "" });
  const [submissionAuditState, setSubmissionAuditState] = useState({ loading: false, data: null, error: "" });
  const [submissionAuditTrailState, setSubmissionAuditTrailState] = useState({ loading: false, data: null, error: "" });
  const [readinessChecklistState, setReadinessChecklistState] = useState({ loading: false, data: null, error: "" });
  const [submissionEvidenceState, setSubmissionEvidenceState] = useState({ loading: false, data: null, error: "" });
  const [submissionEvidenceBundleState, setSubmissionEvidenceBundleState] = useState({ loading: false, data: null, error: "" });
  const [submissionPrintableReportState, setSubmissionPrintableReportState] = useState({ loading: false, data: null, error: "" });
  const [submissionEvidenceSnapshotState, setSubmissionEvidenceSnapshotState] = useState({ loading: false, data: null, error: "" });
  const [submissionComplianceArchiveState, setSubmissionComplianceArchiveState] = useState({ loading: false, data: null, error: "" });
  const [submissionProofState, setSubmissionProofState] = useState({ loading: false, data: null, error: "" });
  const [submissionProofForm, setSubmissionProofForm] = useState(submissionProofFormFromRecord({}));
  const [manualCompletionState, setManualCompletionState] = useState({ loading: false, data: null, error: "" });
  const [manualCompletionForm, setManualCompletionForm] = useState(manualCompletionFormFromRecord({}));

  useEffect(() => {
    let cancelled = false;
    async function loadSubmissions() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const [results, dryRunResults, binderResults] = await Promise.all([
        Promise.all(SUBMISSION_ENDPOINTS.map((path) => fetchEndpoint(path))),
        Promise.all(DRY_RUN_ENDPOINTS.map((path) => fetchEndpoint(path))),
        Promise.all(BINDER_ENDPOINTS.map((path) => fetchEndpoint(path))),
      ]);
      if (cancelled) return;

      const binders = extractSubmissionBinders(binderResults);
      const records = [...results, ...dryRunResults]
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeSubmissionRecord(record, record._sourcePath));

      const merged = mergeSubmissions(records).filter((submission) => submission.rfq_reference !== "RFQ" || submission.title !== "RFQ");
      const baseRows = merged.length ? merged : binders.length ? binders.map(submissionFromBinder) : DEMO_SUBMISSIONS;
      const enrichedRows = attachBindersToSubmissions(baseRows, binders);
      setSubmissionBinders(binders);
      setSubmissions(enrichedRows);
      setEndpointState({
        loading: false,
        results,
        dryRunResults,
        binderResults,
        error: results.some((result) => result.ok) || dryRunResults.some((result) => result.ok) || binderResults.some((result) => result.ok) ? "" : "No submission endpoints responded with usable data.",
      });
    }

    loadSubmissions();
    return () => {
      cancelled = true;
    };
  }, []);

  const submissionStatuses = useMemo(() => ["All", ...uniqueBy(submissions.map((submission) => submission.submission_status), (item) => item).filter(Boolean)], [submissions]);
  const dryRunStatuses = useMemo(() => ["All", ...uniqueBy(submissions.map((submission) => submission.dry_run_status), (item) => item).filter(Boolean)], [submissions]);
  const selectedSubmission = useMemo(() => submissions.find((submission) => submission.id === selectedId), [submissions, selectedId]);

  const filteredSubmissions = useMemo(() => {
    const term = query.trim().toLowerCase();
    return submissions.filter((submission) => {
      const haystack = `${submission.rfq_reference} ${submission.title} ${submission.buyer} ${submission.submission_status}`.toLowerCase();
      const readinessMatch =
        readiness === "All" ||
        (readiness === "Ready >=80" && submission.upload_readiness_score >= 80) ||
        (readiness === "Review 50-79" && submission.upload_readiness_score >= 50 && submission.upload_readiness_score < 80) ||
        (readiness === "Blocked <50" && submission.upload_readiness_score < 50) ||
        (readiness === "Missing Artifacts" && submission.missing_artifacts.length > 0);
      const urgencyDays = daysUntil(submission.closing_date);
      const urgencyMatch =
        urgency === "All" ||
        (urgency === "Overdue" && urgencyDays < 0) ||
        (urgency === "0-2 Days" && urgencyDays >= 0 && urgencyDays <= 2) ||
        (urgency === "3-7 Days" && urgencyDays >= 3 && urgencyDays <= 7) ||
        (urgency === "8+ Days" && urgencyDays > 7);
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || submission.province === province) &&
        (submissionStatus === "All" || submission.submission_status === submissionStatus) &&
        (dryRunStatus === "All" || submission.dry_run_status === dryRunStatus) &&
        readinessMatch &&
        (!blockersOnly || submission.blockers.length > 0) &&
        urgencyMatch
      );
    });
  }, [blockersOnly, dryRunStatus, province, query, readiness, submissions, submissionStatus, urgency]);

  const summary = useMemo(() => ({
    total: submissions.length,
    ready: submissions.filter((submission) => submission.upload_readiness_score >= 80).length,
    dryRunReview: submissions.filter((submission) => /dry|review/i.test(submission.dry_run_status)).length,
    blocked: submissions.filter((submission) => submission.blockers.length > 0 || submission.upload_readiness_score < 50).length,
  }), [submissions]);

  const focusedSubmission = selectedSubmission || filteredSubmissions[0] || submissions[0] || DEMO_SUBMISSIONS[0];
  const focusedBinder = focusedSubmission?.submission_binder || submissionBinders[0] || null;
  const gateBinder = selectedSubmission ? selectedSubmission.submission_binder : focusedBinder;
  const gatePackId = gateBinder?.pack_id || "";
  const gateRfqReference = selectedSubmission?.rfq_reference || gateBinder?.rfq_reference || "";
  const authenticatedSession = authState?.session || null;
  const proofLoadBlockedReason = operatorBlockedReason(authenticatedSession, "proof_load");
  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const dryRunCount = endpointState.dryRunResults.filter((result) => result.ok).length;
  const binderProbeCount = endpointState.binderResults.filter((result) => result.ok).length;
  const usingDemo = submissions.some((submission) => submission._demo);

  useEffect(() => {
    if (!gatePackId || !proofLoadBlockedReason) return;
    setSubmissionProofState({ loading: false, data: null, error: proofLoadBlockedReason });
    setSubmissionProofForm(submissionProofFormFromRecord({}));
  }, [gatePackId, proofLoadBlockedReason]);

  useEffect(() => {
    let cancelled = false;
    async function loadSubmissionGate() {
      if (!gatePackId) {
        setSubmissionGateState({ loading: false, data: null, error: "" });
        setSubmissionGateSummaryState({ loading: false, data: null, error: "" });
        setSubmissionChecklistState({ loading: false, data: null, error: "" });
        setSubmissionAuditState({ loading: false, data: null, error: "" });
        setSubmissionAuditTrailState({ loading: false, data: null, error: "" });
        setReadinessChecklistState({ loading: false, data: null, error: "" });
        setSubmissionEvidenceState({ loading: false, data: null, error: "" });
        setSubmissionEvidenceBundleState({ loading: false, data: null, error: "" });
        setSubmissionPrintableReportState({ loading: false, data: null, error: "" });
        setSubmissionEvidenceSnapshotState({ loading: false, data: null, error: "" });
        setSubmissionComplianceArchiveState({ loading: false, data: null, error: "" });
        setSubmissionProofState({ loading: false, data: null, error: "" });
        setSubmissionProofForm(submissionProofFormFromRecord({}));
        setManualCompletionState({ loading: false, data: null, error: "" });
        setManualCompletionForm(manualCompletionFormFromRecord({}));
        return;
      }
      setSubmissionGateState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionGateSummaryState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionChecklistState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionAuditState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionAuditTrailState((prev) => ({ ...prev, loading: true, error: "" }));
      setReadinessChecklistState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionEvidenceState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionEvidenceBundleState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionPrintableReportState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionEvidenceSnapshotState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionComplianceArchiveState((prev) => ({ ...prev, loading: true, error: "" }));
      setSubmissionProofState((prev) => ({ ...prev, loading: true, error: "" }));
      setManualCompletionState((prev) => ({ ...prev, loading: true, error: "" }));
      const [result, summaryResult, checklistResult, auditResult, auditTrailResult, readinessChecklistResult, evidenceResult, evidenceBundleResult, evidenceSnapshotResult, archiveListResult, proofResult, manualCompletionResult] = await Promise.all([
        fetchEndpoint(submissionGatePath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionGateSummaryPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionChecklistPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionAuditLogPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionAuditTrailPath(gatePackId)),
        fetchEndpoint(submissionReadinessChecklistPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionEvidenceManifestPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionEvidenceBundlePath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionEvidenceSnapshotPath(gatePackId, gateRfqReference)),
        fetchEndpoint(submissionComplianceArchivesPath(gatePackId)),
        proofLoadBlockedReason
          ? Promise.resolve({ ok: true, data: null, skipped: true })
          : fetchEndpoint(submissionProofPath(gatePackId)),
        fetchEndpoint(submissionManualCompletionPath(gatePackId)),
      ]);
      if (cancelled) return;
      setSubmissionGateState({
        loading: false,
        data: result.ok ? result.data : null,
        error: result.ok ? "" : result.error || "Submission gate endpoint did not respond.",
      });
      setSubmissionGateSummaryState({
        loading: false,
        data: summaryResult.ok ? summaryResult.data : null,
        error: summaryResult.ok ? "" : summaryResult.error || "Submission pack summary endpoint did not respond.",
      });
      setSubmissionChecklistState({
        loading: false,
        data: checklistResult.ok ? checklistResult.data : null,
        error: checklistResult.ok ? "" : checklistResult.error || "Manual checklist endpoint did not respond.",
      });
      setSubmissionAuditState({
        loading: false,
        data: auditResult.ok ? auditResult.data : null,
        error: auditResult.ok ? "" : auditResult.error || "Audit log endpoint did not respond.",
      });
      setSubmissionAuditTrailState({
        loading: false,
        data: auditTrailResult.ok ? auditTrailResult.data : null,
        error: auditTrailResult.ok ? "" : auditTrailResult.error || "Audit trail endpoint did not respond.",
      });
      setReadinessChecklistState({
        loading: false,
        data: readinessChecklistResult.ok ? readinessChecklistResult.data : null,
        error: readinessChecklistResult.ok ? "" : readinessChecklistResult.error || "Readiness checklist endpoint did not respond.",
      });
      setSubmissionEvidenceState({
        loading: false,
        data: evidenceResult.ok ? evidenceResult.data : null,
        error: evidenceResult.ok ? "" : evidenceResult.error || "Evidence manifest endpoint did not respond.",
      });
      setSubmissionEvidenceBundleState({
        loading: false,
        data: evidenceBundleResult.ok ? evidenceBundleResult.data : null,
        error: evidenceBundleResult.ok ? "" : evidenceBundleResult.error || "Evidence bundle endpoint did not respond.",
      });
      setSubmissionPrintableReportState({ loading: false, data: null, error: "" });
      setSubmissionEvidenceSnapshotState({
        loading: false,
        data: evidenceSnapshotResult.ok ? evidenceSnapshotResult.data : null,
        error: evidenceSnapshotResult.ok ? "" : evidenceSnapshotResult.error || "Evidence snapshot endpoint did not respond.",
      });
      setSubmissionComplianceArchiveState({
        loading: false,
        data: archiveListResult.ok ? archiveListResult.data : null,
        error: archiveListResult.ok ? "" : archiveListResult.error || "Compliance archives endpoint did not respond.",
      });
      const proofData = proofResult.ok ? proofResult.data : null;
      setSubmissionProofState({
        loading: false,
        data: proofData,
        error: proofLoadBlockedReason || (proofResult.ok ? "" : proofResult.error || "Submission proof endpoint did not respond."),
      });
      if (proofResult.status === 401) {
        onRefreshAuth?.();
      }
      if (proofData?.status === "ok" && proofData?.submission_proof) {
        setSubmissionProofForm(submissionProofFormFromRecord(proofData.submission_proof));
      }
      const manualCompletionData = manualCompletionResult.ok ? manualCompletionResult.data : null;
      setManualCompletionState({
        loading: false,
        data: manualCompletionData,
        error: manualCompletionResult.ok ? "" : manualCompletionResult.error || "Manual completion endpoint did not respond.",
      });
      if (manualCompletionData?.status === "ok" && manualCompletionData?.manual_completion) {
        setManualCompletionForm(manualCompletionFormFromRecord(manualCompletionData.manual_completion));
      }
    }

    loadSubmissionGate();
    return () => {
      cancelled = true;
    };
  }, [gatePackId, gateRfqReference, proofLoadBlockedReason, authState?.session?.operator?.operator_id]);

  function openSubmission(submission) {
    setSelectedId(submission.id);
    setActiveTab("Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  function onAuthFormChange(field, value) {
    setAuthForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleAuthLogin() {
    if (!onLogin) return;
    const result = await onLogin({
      operator_id: authForm.operator_id,
      password: authForm.password,
    });
    await onRefreshAuth?.();
    if (result?.authenticated) {
      setAuthForm((prev) => ({ ...prev, password: "" }));
    }
  }

  async function handleAuthLogout() {
    await onLogout?.();
    await onRefreshAuth?.();
  }

  async function handleAuthBootstrap() {
    if (!onBootstrapAdmin) return;
    const result = await onBootstrapAdmin({
      operator_id: authForm.bootstrap_operator_id,
      display_name: authForm.bootstrap_display_name,
      password: authForm.bootstrap_password,
    });
    if (result?.status === "ok") {
      setAuthForm((prev) => ({
        ...prev,
        operator_id: prev.operator_id || authForm.bootstrap_operator_id,
        bootstrap_password: "",
      }));
    }
    await onRefreshAuth?.();
  }

  async function refreshManualChecklist() {
    if (!gatePackId) return;
    setSubmissionChecklistState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionChecklistPath(gatePackId, gateRfqReference));
    setSubmissionChecklistState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Manual checklist endpoint did not respond.",
    });
  }

  async function refreshSubmissionGate() {
    if (!gatePackId) return;
    setSubmissionGateState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionGatePath(gatePackId, gateRfqReference));
    setSubmissionGateState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Submission gate endpoint did not respond.",
    });
  }

  async function refreshSubmissionPackSummary() {
    if (!gatePackId) return;
    setSubmissionGateSummaryState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionGateSummaryPath(gatePackId, gateRfqReference));
    setSubmissionGateSummaryState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Submission pack summary endpoint did not respond.",
    });
  }

  async function refreshSubmissionProof() {
    if (!gatePackId) return;
    if (proofLoadBlockedReason) {
      setSubmissionProofState({ loading: false, data: null, error: proofLoadBlockedReason });
      return;
    }
    setSubmissionProofState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionProofPath(gatePackId));
    const proofData = result.ok ? result.data : null;
    setSubmissionProofState({
      loading: false,
      data: proofData,
      error: result.ok ? "" : result.error || "Submission proof endpoint did not respond.",
    });
    if (result.status === 401) await onRefreshAuth?.();
    if (proofData?.status === "ok" && proofData?.submission_proof) {
      setSubmissionProofForm(submissionProofFormFromRecord(proofData.submission_proof));
    }
  }

  async function refreshAuditLog() {
    if (!gatePackId) return;
    setSubmissionAuditState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionAuditLogPath(gatePackId, gateRfqReference));
    setSubmissionAuditState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Audit log endpoint did not respond.",
    });
  }

  async function refreshAuditTrail() {
    if (!gatePackId) return;
    setSubmissionAuditTrailState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionAuditTrailPath(gatePackId));
    setSubmissionAuditTrailState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Audit trail endpoint did not respond.",
    });
  }

  async function refreshReadinessChecklist() {
    if (!gatePackId) return;
    setReadinessChecklistState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionReadinessChecklistPath(gatePackId, gateRfqReference));
    setReadinessChecklistState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Readiness checklist endpoint did not respond.",
    });
  }

  async function refreshEvidenceManifest() {
    if (!gatePackId) return;
    setSubmissionEvidenceState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionEvidenceManifestPath(gatePackId, gateRfqReference));
    setSubmissionEvidenceState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Evidence manifest endpoint did not respond.",
    });
  }

  async function refreshEvidenceBundle() {
    if (!gatePackId) return;
    setSubmissionEvidenceBundleState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionEvidenceBundlePath(gatePackId, gateRfqReference));
    setSubmissionEvidenceBundleState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Evidence bundle endpoint did not respond.",
    });
  }

  async function refreshPrintableReport() {
    if (!gatePackId) return;
    setSubmissionPrintableReportState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchTextEndpoint(submissionPrintableReportPath(gatePackId, gateRfqReference));
    const preview = result.ok ? parsePrintableReportPreview(result.data) : null;
    setSubmissionPrintableReportState({
      loading: false,
      data: preview,
      error: result.ok ? "" : result.error || "Printable report endpoint did not respond.",
    });
  }

  async function refreshEvidenceSnapshot() {
    if (!gatePackId) return;
    setSubmissionEvidenceSnapshotState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionEvidenceSnapshotPath(gatePackId, gateRfqReference));
    setSubmissionEvidenceSnapshotState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Evidence snapshot endpoint did not respond.",
    });
  }

  async function refreshComplianceArchives() {
    if (!gatePackId) return;
    setSubmissionComplianceArchiveState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await fetchEndpoint(submissionComplianceArchivesPath(gatePackId));
    setSubmissionComplianceArchiveState({
      loading: false,
      data: result.ok ? result.data : null,
      error: result.ok ? "" : result.error || "Compliance archives endpoint did not respond.",
    });
  }

  async function saveSubmissionProofRecord() {
    if (!gatePackId) return;
    const blockedReason = operatorBlockedReason(authenticatedSession, "proof_save");
    if (blockedReason) {
      setSubmissionProofState((prev) => ({ ...prev, loading: false, error: blockedReason }));
      if (blockedReason.toLowerCase().includes("login required")) await onRefreshAuth?.();
      return;
    }
    setSubmissionProofState((prev) => ({ ...prev, loading: true, error: "" }));
    const payload = {
      submitted_by: submissionProofForm.submitted_by,
      submission_timestamp: submissionProofForm.submission_timestamp,
      portal_name: submissionProofForm.portal_name,
      portal_reference: submissionProofForm.portal_reference,
      proof_notes: submissionProofForm.proof_notes,
      buyer_reference: submissionProofForm.buyer_reference,
      uploaded_files: submissionProofForm.uploaded_files
        .split(/\n|;|\|/)
        .map((item) => item.trim())
        .filter(Boolean),
      screenshot_paths: submissionProofForm.screenshot_paths
        .split(/\n|;|\|/)
        .map((item) => item.trim())
        .filter(Boolean),
      confirmation_message: submissionProofForm.confirmation_message,
      screenshot_notes: submissionProofForm.screenshot_notes,
      email_proof: submissionProofForm.email_proof,
      portal_proof: submissionProofForm.portal_proof,
      receipt_reference: submissionProofForm.receipt_reference,
      proof_reference: submissionProofForm.proof_reference,
    };
    const result = await postEndpoint(submissionProofPath(gatePackId), payload);
    if (!result.ok) {
      setSubmissionProofState({ loading: false, data: null, error: result.error || "Submission proof could not be saved." });
      if (result.status === 401) await onRefreshAuth?.();
      return;
    }
    const proofData = result.data || null;
    setSubmissionProofState({ loading: false, data: proofData, error: "" });
    if (proofData?.submission_proof) {
      setSubmissionProofForm(submissionProofFormFromRecord(proofData.submission_proof));
    }
    await Promise.all([
      refreshSubmissionGate(),
      refreshSubmissionPackSummary(),
      refreshAuditTrail(),
      refreshReadinessChecklist(),
      refreshEvidenceManifest(),
      refreshEvidenceBundle(),
      refreshPrintableReport(),
      refreshEvidenceSnapshot(),
    ]);
  }

  async function createComplianceArchive() {
    if (!gatePackId) return;
    const blockedReason = operatorBlockedReason(authenticatedSession, "archive_create");
    if (blockedReason) {
      setSubmissionComplianceArchiveState((prev) => ({ ...prev, loading: false, error: blockedReason }));
      if (blockedReason.toLowerCase().includes("login required")) await onRefreshAuth?.();
      return;
    }
    setSubmissionComplianceArchiveState((prev) => ({ ...prev, loading: true, error: "" }));
    const result = await postEndpoint(submissionComplianceArchivePath(gatePackId, gateRfqReference), {});
    if (!result.ok) {
      setSubmissionComplianceArchiveState({ loading: false, data: null, error: result.error || "Compliance archive could not be created." });
      if (result.status === 401) await onRefreshAuth?.();
      return;
    }
    await refreshComplianceArchives();
  }

  async function downloadSubmissionProofJson() {
    if (!gatePackId) return;
    const blockedReason = operatorBlockedReason(authenticatedSession, "proof_export");
    if (blockedReason) {
      setSubmissionProofState((prev) => ({ ...prev, error: blockedReason }));
      if (blockedReason.toLowerCase().includes("login required")) await onRefreshAuth?.();
      return;
    }
    const result = await downloadEndpoint(
      submissionProofExportPath(gatePackId),
      `${gatePackId}-submission-proof.json`,
      {},
    );
    if (!result.ok) {
      setSubmissionProofState((prev) => ({ ...prev, error: result.error || "Submission proof export could not be downloaded." }));
      if (result.status === 401) await onRefreshAuth?.();
    }
  }

  async function downloadComplianceArchiveZip(archiveId = "latest") {
    if (!gatePackId) return;
    const blockedReason = operatorBlockedReason(authenticatedSession, "archive_export");
    if (blockedReason) {
      setSubmissionComplianceArchiveState((prev) => ({ ...prev, error: blockedReason }));
      if (blockedReason.toLowerCase().includes("login required")) await onRefreshAuth?.();
      return;
    }
    const path = archiveId === "latest"
      ? submissionComplianceArchiveLatestZipPath(gatePackId)
      : submissionComplianceArchiveZipPath(gatePackId, archiveId);
    const result = await downloadEndpoint(
      path,
      `${gatePackId}-${archiveId}-compliance-archive.zip`,
      {},
    );
    if (!result.ok) {
      setSubmissionComplianceArchiveState((prev) => ({ ...prev, error: result.error || "Compliance archive ZIP could not be downloaded." }));
      if (result.status === 401) await onRefreshAuth?.();
    }
  }

  function onManualCompletionChange(field, value) {
    setManualCompletionForm((prev) => ({ ...prev, [field]: value }));
  }

  function onSubmissionProofChange(field, value) {
    setSubmissionProofForm((prev) => ({ ...prev, [field]: value }));
  }

  async function saveManualCompletionRecord() {
    if (!gatePackId) return;
    setManualCompletionState((prev) => ({ ...prev, loading: true, error: "" }));
    const payload = {
      submitted_by: manualCompletionForm.submitted_by,
      submitted_at: manualCompletionForm.submitted_at,
      portal_name: manualCompletionForm.portal_name,
      portal_reference: manualCompletionForm.portal_reference,
      notes: manualCompletionForm.notes,
      uploaded_file_names: manualCompletionForm.uploaded_file_names
        .split(/\n|;|\|/)
        .map((item) => item.trim())
        .filter(Boolean),
    };
    const result = await postEndpoint(submissionManualCompletionPath(gatePackId), payload);
    if (!result.ok) {
      setManualCompletionState({ loading: false, data: null, error: result.error || "Manual completion record could not be saved." });
      return;
    }
    const manualCompletionData = result.data || null;
    setManualCompletionState({ loading: false, data: manualCompletionData, error: "" });
    if (manualCompletionData?.manual_completion) {
      setManualCompletionForm(manualCompletionFormFromRecord(manualCompletionData.manual_completion));
    }
    await Promise.all([refreshSubmissionGate(), refreshAuditTrail(), refreshReadinessChecklist(), refreshEvidenceBundle(), refreshEvidenceSnapshot()]);
  }

  return (
    <section className="submission-workspace" id="submission-centre-workspace">
      <SafetyBanner />

      <div className="submission-hero card">
        <div>
          <p className="eyebrow">Submission Centre</p>
          <h1>Submission Centre Workspace</h1>
          <p className="muted">Read-only dry-run and upload readiness view probing {API_BASE}. Dry-run candidates are reviewed without execution.</p>
        </div>
        <div className="submission-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${SUBMISSION_ENDPOINTS.length} endpoints live · ${dryRunCount}/${DRY_RUN_ENDPOINTS.length} dry-run probes · ${binderProbeCount}/${BINDER_ENDPOINTS.length} binder probes`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="submission-summary-grid">
        <div className="submission-summary-card"><span>Candidates</span><b>{summary.total}</b></div>
        <div className="submission-summary-card good"><span>Upload Ready</span><b>{summary.ready}</b></div>
        <div className="submission-summary-card blue"><span>Dry-Run Review</span><b>{summary.dryRunReview}</b></div>
        <div className="submission-summary-card amber"><span>Blocked</span><b>{summary.blocked}</b></div>
      </div>

      <div className="submission-toolbar card">
        <label className="submission-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search RFQ, buyer, status" />
        </label>
        <label><Filter size={15} /><select value={province} onChange={(event) => setProvince(event.target.value)}>{PROVINCES.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={submissionStatus} onChange={(event) => setSubmissionStatus(event.target.value)}>{submissionStatuses.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={dryRunStatus} onChange={(event) => setDryRunStatus(event.target.value)}>{dryRunStatuses.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={readiness} onChange={(event) => setReadiness(event.target.value)}>{["All", "Ready >=80", "Review 50-79", "Blocked <50", "Missing Artifacts"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={urgency} onChange={(event) => setUrgency(event.target.value)}>{["All", "Overdue", "0-2 Days", "3-7 Days", "8+ Days"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <button className={blockersOnly ? "active" : ""} type="button" onClick={() => setBlockersOnly((value) => !value)}>
          <ShieldAlert size={15} />
          Blockers only
        </button>
      </div>

      {endpointState.error ? <div className="submission-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="submission-warning"><UploadCloud size={16} />No live submission rows were found. Showing a non-destructive workspace preview row.</div> : null}

      <Suspense fallback={<div className="submission-binder-section card"><div className="submission-binder-empty">Loading binder readiness panel...</div></div>}>
        <LazySubmissionBinderReadinessPanel
          binders={submissionBinders}
          focusedBinder={focusedBinder}
          operatorState={operatorState}
          onOperatorAction={setLocalAction}
        />
      </Suspense>

      <SubmissionGateCard
        authState={authState}
        authForm={authForm}
        onAuthFormChange={onAuthFormChange}
        onAuthLogin={handleAuthLogin}
        onAuthLogout={handleAuthLogout}
        onAuthBootstrap={handleAuthBootstrap}
        gateState={submissionGateState}
        summaryState={submissionGateSummaryState}
        checklistState={submissionChecklistState}
        auditState={submissionAuditState}
        auditTrailState={submissionAuditTrailState}
        readinessChecklistState={readinessChecklistState}
        evidenceState={submissionEvidenceState}
        evidenceBundleState={submissionEvidenceBundleState}
        submissionPrintableReportState={submissionPrintableReportState}
        submissionEvidenceSnapshotState={submissionEvidenceSnapshotState}
        submissionComplianceArchiveState={submissionComplianceArchiveState}
        submissionProofState={submissionProofState}
        submissionProofForm={submissionProofForm}
        onSubmissionProofChange={onSubmissionProofChange}
        onSubmissionProofSave={saveSubmissionProofRecord}
        onSubmissionProofRequest={refreshSubmissionProof}
        onSubmissionProofDownload={downloadSubmissionProofJson}
        manualCompletionState={manualCompletionState}
        manualCompletionForm={manualCompletionForm}
        onManualCompletionChange={onManualCompletionChange}
        onManualCompletionSave={saveManualCompletionRecord}
        onPrintableReportRequest={refreshPrintableReport}
        packId={gatePackId}
        onSummaryRequest={refreshSubmissionPackSummary}
        onChecklistRequest={refreshManualChecklist}
        onAuditRequest={refreshAuditLog}
        onAuditTrailRequest={refreshAuditTrail}
        onReadinessChecklistRequest={refreshReadinessChecklist}
        onEvidenceRequest={refreshEvidenceManifest}
        onEvidenceBundleRequest={refreshEvidenceBundle}
        onEvidenceSnapshotRequest={refreshEvidenceSnapshot}
        onComplianceArchiveCreateRequest={createComplianceArchive}
        onComplianceArchivesRequest={refreshComplianceArchives}
        onComplianceArchiveDownload={downloadComplianceArchiveZip}
      />

      <div className="submission-table-card card">
        <div className="card-head">
          <h2>Dry-Run / Upload Readiness Queue</h2>
          <span>{filteredSubmissions.length} visible</span>
        </div>
        <div className="submission-table-scroll">
          <table className="submission-table">
            <thead>
              <tr>
                <th>RFQ</th>
                <th>Buyer</th>
                <th>Province</th>
                <th>Submission</th>
                <th>Dry-Run</th>
                <th>Readiness</th>
                <th>Missing</th>
                <th>Closing</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredSubmissions.map((submission, index) => {
                const close = urgencyMeta(submission.closing_date);
                return (
                  <tr key={`${submission.id}-${index}`} onClick={() => openSubmission(submission)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openSubmission(submission)}>
                    <td><b>{submission.rfq_reference}</b><span>{submission.title}</span></td>
                    <td>{submission.buyer}</td>
                    <td>{submission.province}</td>
                    <td><span className="pill">{operatorState[submission.id] || submission.submission_status}</span></td>
                    <td><StatusChip label="" status={submission.dry_run_status} /></td>
                    <td><ScoreChip label="Upload" score={submission.upload_readiness_score} /></td>
                    <td>{submission.missing_artifacts.length}</td>
                    <td><span className={`submission-urgency ${close.tone}`}><Clock3 size={14} />{close.label}</span></td>
                    <td><button type="button" className="submission-row-button" onClick={(event) => { event.stopPropagation(); openSubmission(submission); }}>Open</button></td>
                  </tr>
                );
              })}
              {!filteredSubmissions.length ? (
                <tr><td colSpan="9"><div className="submission-empty-inline">No submission candidates match the current filters.</div></td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="submission-panels">
        <PanelShell title="Required Artifacts Checklist" icon={FileCheck2}>
          <ArtifactChecklist required={focusedSubmission.required_artifacts} found={focusedSubmission.found_artifacts} missing={focusedSubmission.missing_artifacts} />
        </PanelShell>
        <PanelShell title="Missing Upload Artifacts" icon={ShieldAlert}>
          <div className="submission-risk-list">
            {(focusedSubmission.missing_artifacts.length ? focusedSubmission.missing_artifacts : ["No missing upload artifacts detected."]).map((item, index) => <p className="submission-risk blocker" key={`missing-${item}-${index}`}>{item}</p>)}
          </div>
        </PanelShell>
        <PanelShell title="Proof Readiness" icon={ShieldCheck}>
          <div className="submission-panel-status"><StatusChip label="Proof" status={focusedSubmission.proof_status} /></div>
          <ArtifactList items={focusedSubmission.proofs} empty="No proof artifacts linked yet." />
        </PanelShell>
        <PanelShell title="Portal Compatibility / Health" icon={Globe2}>
          <div className="submission-panel-status"><StatusChip label="Portal" status={focusedSubmission.portal_status} /><StatusChip label="Dry-Run" status={focusedSubmission.dry_run_status} /></div>
          <p className="submission-panel-note">Portal execution is locked. This panel is compatibility/readiness only.</p>
        </PanelShell>
        <PanelShell title="Blockers & Risks" icon={AlertTriangle}>
          <div className="submission-risk-list">
            {(focusedSubmission.blockers.length ? focusedSubmission.blockers : ["No hard blockers detected."]).map((item, index) => <p className="submission-risk blocker" key={`blocker-${item}-${index}`}>{item}</p>)}
            {focusedSubmission.risks.map((item, index) => <p className="submission-risk" key={`risk-${item}-${index}`}>{item}</p>)}
          </div>
        </PanelShell>
      </div>

      <DetailDrawer
        submission={selectedSubmission}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
      />
    </section>
  );
}
