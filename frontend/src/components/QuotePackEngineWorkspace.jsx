import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock3,
  FileArchive,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Filter,
  Layers3,
  PackageCheck,
  PauseCircle,
  Search,
  ShieldAlert,
  ThumbsUp,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";

const REQUEST_TIMEOUT_MS = 8000;
const QUOTE_PACK_LATEST_ENDPOINT = "/quote-compilation/packs/latest";

const QUOTE_ENDPOINTS = [
  "/quote-compilation/status",
  "/quote-compilation/candidates",
  "/rfq-lifecycle/status",
  "/rfq-lifecycle/recent",
  "/rfq-lifecycle/report",
  "/submission-history/recent",
  "/submission-pack/status",
  "/quote-engine/status",
  "/portal-submission/status",
  "/health",
];

const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
const DRAWER_TABS = ["Overview", "Pricing Schedule", "BOQ", "Returnables", "Generated Files", "Risks"];
const RETURNABLE_STATUS_OPTIONS = ["missing", "available", "completed", "not_applicable", "needs_review"];

const DEMO_QUOTE_PACKS = [
  {
    id: "demo-quote-pack-engine",
    rfq_reference: "RFQ-QP-DEMO-001",
    title: "Supply and delivery quote pack preview",
    buyer: "Demo Buyer",
    province: "GP",
    closing_date: new Date(Date.now() + 5 * 86400000).toISOString(),
    quote_status: "Prep Review",
    pricing_schedule_status: "Detected",
    boq_status: "Detected",
    sbd_status: "Partial",
    returnables_status: "Missing Items",
    estimated_value: 185000,
    estimated_profit: 46250,
    margin_percent: 25,
    quote_readiness_score: 76,
    missing_items: ["Signed SBD declaration", "Tax compliance PIN"],
    documents: [{ name: "Buyer RFQ form.pdf", type: "Buyer Form" }],
    generated_files: [{ name: "LMCP quote pack preview.pdf", type: "Quote Pack" }],
    pricing_schedules: [{ name: "Pricing schedule.xlsx", type: "Pricing Schedule", status: "Detected" }],
    boqs: [{ name: "Bill of quantities.xlsx", type: "BOQ", status: "Detected" }],
    returnables: [{ name: "SBD 4", status: "Ready" }, { name: "SBD declaration", status: "Missing" }],
    risks: ["Demo fallback data shown because live quote-pack records did not load"],
    recommended_next_step: "Hold for missing docs",
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
  const raw = safeText(value || record.quote_status || record.pack_status || record.pipeline_status || record.lifecycle_state || record.status, "Draft");
  const lower = raw.toLowerCase();
  if (lower.includes("reject") || lower.includes("fail") || lower.includes("block")) return "Blocked";
  if (lower.includes("hold") || lower.includes("missing")) return "On Hold";
  if (lower.includes("ready") && lower.includes("submit")) return "Submission Ready";
  if (lower.includes("ready") || lower.includes("approved")) return "Quote Ready";
  if (lower.includes("price")) return "Pricing";
  if (lower.includes("pack")) return "Pack Prep";
  if (lower.includes("review")) return "Prep Review";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeReadinessStatus(value, present = false) {
  const raw = safeText(value, present ? "Detected" : "Missing");
  const lower = raw.toLowerCase();
  if (lower.includes("complete") || lower.includes("ready") || lower.includes("detected") || lower.includes("done")) return "Ready";
  if (lower.includes("partial") || lower.includes("review") || lower.includes("progress")) return "Partial";
  if (lower.includes("missing") || lower.includes("fail") || lower.includes("block")) return "Missing";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeArtifact(value, type = "Document") {
  if (!value) return null;
  if (typeof value === "string") {
    return { name: value.split("/").pop() || value, url: value.startsWith("http") || value.startsWith("/") ? value : "", type };
  }
  if (typeof value !== "object") return null;
  const url = safeText(pick(value, ["url", "href", "path", "file_path", "local_path", "download_url", "source_url", "preview_url"]));
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

function inferArtifacts(documents, pattern, type) {
  return uniqueBy(
    documents
      .filter((doc) => pattern.test(`${doc.name} ${doc.type}`))
      .map((doc) => ({ ...doc, type })),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function isQuoteLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(rfq|tender|quote|pack|pricing|boq|sbd|returnable|submission|buyer|closing|document|reference|title|description)/.test(keys);
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

    if (isQuoteLike(value)) {
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

function deriveMissingItems(record, pricingSchedules, boqs, returnables) {
  const explicit = asArray(pick(record, ["missing_items", "missing_returnables", "missing_documents", "missing_forms", "readiness_gaps", "upload_missing"]))
    .map((item) => safeText(typeof item === "object" ? pick(item, ["name", "label", "field", "document", "reason"]) : item))
    .filter(Boolean);
  const inferred = [];
  if (!pricingSchedules.length) inferred.push("Pricing schedule");
  if (!boqs.length) inferred.push("BOQ");
  const missingReturnables = returnables.filter((item) => safeText(item.status).toLowerCase().includes("missing"));
  missingReturnables.forEach((item) => inferred.push(item.name));
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase()).slice(0, 10);
}

function normalizeReturnables(record) {
  const values = asArray(pick(record, ["returnables", "sbd_forms", "sbd_documents", "returnable_forms", "compliance_documents"]));
  return values
    .map((item) => {
      if (typeof item === "string") return { name: item, status: "Unknown" };
      if (!item || typeof item !== "object") return null;
      return {
        name: safeText(pick(item, ["name", "title", "label", "document", "form"]), "Returnable"),
        status: normalizeReadinessStatus(pick(item, ["status", "state", "readiness"]), false),
      };
    })
    .filter(Boolean);
}

function deriveScore(record, pricingStatus, boqStatus, sbdStatus, returnablesStatus, missingItems, generatedFiles) {
  const explicit = pick(record, ["quote_readiness_score", "readiness_score", "pack_readiness_score", "quote_score"]);
  if (explicit !== undefined) return normalizeScore(explicit);
  const statusValues = [pricingStatus, boqStatus, sbdStatus, returnablesStatus];
  const statusScore = statusValues.reduce((sum, status) => {
    if (status === "Ready") return sum + 20;
    if (status === "Partial") return sum + 10;
    return sum;
  }, 10);
  const generatedScore = Math.min(15, generatedFiles.length * 5);
  const penalty = Math.min(45, missingItems.length * 10);
  return Math.max(0, Math.min(100, statusScore + generatedScore - penalty));
}

function normalizeRisks(record, missingItems, pricingStatus, boqStatus) {
  const explicit = asArray(pick(record, ["risks", "risk_flags", "alerts", "warnings", "blockers"])).map((item) => safeText(item)).filter(Boolean);
  const inferred = [];
  if (missingItems.length) inferred.push(`${missingItems.length} quote-pack item(s) missing`);
  if (pricingStatus === "Missing") inferred.push("Pricing schedule not ready");
  if (boqStatus === "Missing") inferred.push("BOQ not ready");
  return uniqueBy([...explicit, ...inferred], (item) => item.toLowerCase()).slice(0, 8);
}

function normalizeQuotePackRecord(record, sourcePath) {
  const readiness = record?.readiness && typeof record.readiness === "object" ? record.readiness : {};
  const artifacts = record?.artifacts && typeof record.artifacts === "object" ? record.artifacts : {};
  const expandedRecord = {
    ...record,
    quote_readiness_score: pick(record, ["quote_readiness_score"]) ?? readiness.quote_readiness_score,
    missing_items: pick(record, ["missing_items"]) ?? readiness.missing_items,
    pricing_schedule_status: pick(record, ["pricing_schedule_status"]) ?? (readiness.pricing_schedule_found === true ? "Detected" : readiness.pricing_schedule_found === false ? "Missing" : undefined),
    boq_status: pick(record, ["boq_status"]) ?? (readiness.boq_found === true ? "Detected" : readiness.boq_found === false ? "Missing" : undefined),
    sbd_status: pick(record, ["sbd_status"]) ?? (readiness.sbd_forms_found === true ? "Detected" : readiness.sbd_forms_found === false ? "Missing" : undefined),
    returnables_status: pick(record, ["returnables_status"]) ?? (readiness.buyer_forms_found && readiness.sbd_forms_found ? "Detected" : undefined),
    buyer_docs: artifacts.buyer_docs,
    pricing_schedules: artifacts.pricing_schedules,
    boqs: artifacts.boqs,
    sbd_forms: artifacts.sbd_forms,
    generated_quote_files: artifacts.generated_quote_files,
  };
  const rfqReference = safeText(
    pick(expandedRecord, ["rfq_reference", "reference", "rfq_number", "buyer_rfq_number", "bid_number", "tender_number", "id", "rfq_id"]),
    "RFQ",
  );
  const title = safeText(pick(expandedRecord, ["title", "description", "name", "opportunity_title", "tender_title", "subject"]), rfqReference);
  const buyer = safeText(pick(expandedRecord, ["buyer", "buyer_name", "department", "organisation", "organization", "client", "entity"]), "Unknown Buyer");
  const province = normalizeProvince(pick(expandedRecord, ["province", "buyer_province", "region", "location"]));
  const documents = uniqueBy(
    [
      ...collectArtifacts(expandedRecord, ["documents", "docs", "files", "attachments", "downloaded_documents", "source_documents", "buyer_forms", "returnable_forms", "buyer_docs"], "Document"),
      ...collectArtifacts(expandedRecord, ["rfq_document", "rfq_pdf", "form", "buyer_form"], "Buyer Form"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const generatedFiles = uniqueBy(
    collectArtifacts(expandedRecord, ["generated_files", "generated_quote_files", "quote_pack_files", "submission_pack", "submission_packs", "pack_files", "generated_documents", "proofs", "receipts"], "Generated File"),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const pricingSchedules = uniqueBy(
    [
      ...collectArtifacts(expandedRecord, ["pricing_schedules", "pricing_schedule", "price_schedule", "pricing", "price_list", "rates"], "Pricing Schedule"),
      ...inferArtifacts([...documents, ...generatedFiles], /\b(pric(e|ing)|schedule|rates?|quotation[-_\s]*form)\b/i, "Pricing Schedule"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const boqs = uniqueBy(
    [
      ...collectArtifacts(expandedRecord, ["boqs", "boq", "bill_of_quantities", "bill_of_quantity"], "BOQ"),
      ...inferArtifacts([...documents, ...generatedFiles], /\b(boq|bill[-_\s]*of[-_\s]*quantit)/i, "BOQ"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const serviceSbdForms = collectArtifacts(expandedRecord, ["sbd_forms"], "SBD").map((item) => ({ name: item.name, status: "Ready" }));
  const returnables = uniqueBy([...normalizeReturnables(expandedRecord), ...serviceSbdForms], (item) => `${item.name}:${item.status}`.toLowerCase());
  const pricingScheduleStatus = normalizeReadinessStatus(pick(expandedRecord, ["pricing_schedule_status", "pricing_status"]), pricingSchedules.length > 0);
  const boqStatus = normalizeReadinessStatus(pick(expandedRecord, ["boq_status", "bill_of_quantities_status"]), boqs.length > 0);
  const sbdStatus = normalizeReadinessStatus(pick(expandedRecord, ["sbd_status", "sbd_completion_status"]), returnables.some((item) => /sbd/i.test(item.name) && item.status === "Ready"));
  const returnablesStatus = normalizeReadinessStatus(pick(expandedRecord, ["returnables_status", "returnable_status"]), returnables.length > 0 && returnables.every((item) => item.status !== "Missing"));
  const missingItems = deriveMissingItems(expandedRecord, pricingSchedules, boqs, returnables);
  const estimatedValue = normalizeNumber(pick(expandedRecord, ["estimated_value", "value", "contract_value", "budget", "amount"]));
  const estimatedProfit = normalizeNumber(pick(expandedRecord, ["estimated_profit", "profit", "total_profit", "gross_profit"]));
  const marginPercent = normalizeNumber(pick(expandedRecord, ["margin_percent", "margin", "profit_margin"]), estimatedValue ? (estimatedProfit / estimatedValue) * 100 : 0);
  const quoteReadinessScore = deriveScore(expandedRecord, pricingScheduleStatus, boqStatus, sbdStatus, returnablesStatus, missingItems, generatedFiles);
  const risks = normalizeRisks(record, missingItems, pricingScheduleStatus, boqStatus);
  const quoteStatus = normalizeStatus(pick(expandedRecord, ["quote_status", "pack_status", "status", "lifecycle_state", "pipeline_status", "stage"]), expandedRecord);
  const id = slug(pick(expandedRecord, ["id", "quote_pack_id", "rfq_id"], "") || `${rfqReference}-${title}`) || `quote-${Math.random().toString(36).slice(2)}`;
  const recommendedNextStep =
    safeText(pick(expandedRecord, ["recommended_next_step", "recommended_action", "next_action", "operator_action"])) ||
    (quoteReadinessScore >= 80 ? "Approve quote pack prep" : missingItems.length ? "Hold for missing docs" : "Mark ready for pricing");

  return {
    id,
    rfq_reference: rfqReference,
    title,
    buyer,
    province,
    closing_date: safeText(pick(expandedRecord, ["closing_date", "closing", "close_date", "deadline", "closing_datetime"])),
    quote_status: quoteStatus,
    pricing_schedule_status: pricingScheduleStatus,
    boq_status: boqStatus,
    sbd_status: sbdStatus,
    returnables_status: returnablesStatus,
    estimated_value: estimatedValue,
    estimated_profit: estimatedProfit,
    margin_percent: marginPercent,
    quote_readiness_score: quoteReadinessScore,
    missing_items: missingItems,
    documents,
    generated_files: generatedFiles,
    pricing_schedules: pricingSchedules,
    boqs,
    returnables,
    risks,
    recommended_next_step: recommendedNextStep,
    _sources: [sourcePath],
    _raw: record,
  };
}

function mergeQuotePacks(records) {
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
      quote_status: existing.quote_status !== "Draft" ? existing.quote_status : record.quote_status,
      documents: uniqueBy([...existing.documents, ...record.documents], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      generated_files: uniqueBy([...existing.generated_files, ...record.generated_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      pricing_schedules: uniqueBy([...existing.pricing_schedules, ...record.pricing_schedules], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      boqs: uniqueBy([...existing.boqs, ...record.boqs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      returnables: uniqueBy([...existing.returnables, ...record.returnables], (item) => `${item.name}:${item.status}`.toLowerCase()),
      missing_items: uniqueBy([...existing.missing_items, ...record.missing_items], (item) => item.toLowerCase()),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      quote_readiness_score: Math.max(existing.quote_readiness_score, record.quote_readiness_score),
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => {
    const urgency = daysUntil(a.closing_date) - daysUntil(b.closing_date);
    if (Number.isFinite(urgency) && urgency !== 0) return urgency;
    return b.quote_readiness_score - a.quote_readiness_score;
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
  if (lower.includes("ready") || lower.includes("detected")) return "green";
  if (lower.includes("partial") || lower.includes("review") || lower.includes("hold")) return "amber";
  if (lower.includes("missing") || lower.includes("block") || lower.includes("reject")) return "red";
  return "neutral";
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
      body: JSON.stringify(payload || {}),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.message || `${response.status} ${response.statusText}`);
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error.message || "request failed" };
  } finally {
    clearTimeout(timeout);
  }
}

function packDetailFromGeneration(result) {
  if (!result?.manifest) return null;
  const manifest = result.manifest;
  return {
    status: result.status || "ok",
    pack_id: manifest.pack_id,
    metadata: {
      pack_id: manifest.pack_id,
      path: result.workspace || "",
      created_at: manifest.created_at,
      rfq_reference: manifest.rfq_reference,
      title: manifest.title,
      buyer: manifest.buyer,
      file_count: (manifest.files || []).length,
      safety: manifest.safety || result.safety || {},
    },
    manifest,
    summary: {
      rfq_reference: manifest.rfq_reference,
      title: manifest.title,
      buyer: manifest.buyer,
      recommended_next_step: result.candidate?.recommended_next_step || "",
      safety: manifest.safety || result.safety || {},
    },
    pricing_schedule_review: {
      pricing_schedule_found: manifest.readiness?.pricing_schedule_found,
      boq_found: manifest.readiness?.boq_found,
      pricing_schedules: result.candidate?.artifacts?.pricing_schedules || [],
      boqs: result.candidate?.artifacts?.boqs || [],
      safety: manifest.safety || result.safety || {},
    },
    returnables_checklist: {
      buyer_forms_found: manifest.readiness?.buyer_forms_found,
      sbd_forms_found: manifest.readiness?.sbd_forms_found,
      buyer_docs: result.candidate?.artifacts?.buyer_docs || [],
      sbd_forms: result.candidate?.artifacts?.sbd_forms || [],
      missing_items: manifest.readiness?.missing_items || [],
      safety: manifest.safety || result.safety || {},
    },
    operator_next_steps: "",
    files: manifest.files || [],
    read_only: true,
    safety: manifest.safety || result.safety || {},
  };
}

function normalizePackFile(file) {
  if (!file || typeof file !== "object") return null;
  const path = safeText(file.path);
  const url = safeText(file.url) || (path.startsWith("runtime/") ? `/runtime/${path.replace(/^runtime\//, "")}` : "");
  return {
    name: safeText(file.name, path.split("/").pop() || "Generated file"),
    type: safeText(file.type, "local_pack_file"),
    path,
    url,
    size_bytes: normalizeNumber(file.size_bytes),
  };
}

function getPackFiles(packDetail) {
  const files = asArray(packDetail?.files).length ? packDetail.files : packDetail?.manifest?.files;
  return asArray(files).map(normalizePackFile).filter(Boolean);
}

function getPackMissingItems(packDetail) {
  return uniqueBy(
    [
      ...asArray(packDetail?.manifest?.readiness?.missing_items),
      ...asArray(packDetail?.returnables_checklist?.missing_items),
    ]
      .map((item) => safeText(item))
      .filter(Boolean),
    (item) => item.toLowerCase(),
  );
}

function ScoreChip({ label, score }) {
  return (
    <span className={`quote-score-chip ${scoreTone(score)}`}>
      <small>{label}</small>
      <b>{score}</b>
    </span>
  );
}

function StatusChip({ label, status }) {
  return (
    <span className={`quote-status-chip ${statusTone(status)}`}>
      <small>{label}</small>
      <b>{status}</b>
    </span>
  );
}

function ArtifactList({ items, empty }) {
  if (!items.length) return <div className="quote-empty-inline">{empty}</div>;
  return (
    <div className="quote-artifact-list">
      {items.map((item, index) => (
        <div className="quote-artifact" key={`${item.name}-${index}`}>
          {item.type === "BOQ" || item.type === "Pricing Schedule" ? <FileSpreadsheet size={16} /> : item.type === "Quote Pack" || item.type === "Generated File" ? <FileArchive size={16} /> : <FileText size={16} />}
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

function Checklist({ items, missingItems }) {
  const rows = items.length ? items : missingItems.map((name) => ({ name, status: "Missing" }));
  if (!rows.length) {
    return (
      <div className="quote-check-row complete">
        <CheckCircle2 size={17} />
        <span>No missing returnables or SBD items detected</span>
      </div>
    );
  }
  return (
    <div className="quote-checklist">
      {rows.map((item, index) => {
        const missing = safeText(item.status).toLowerCase().includes("missing");
        return (
          <div className={`quote-check-row ${missing ? "missing" : "complete"}`} key={`${item.name}-${index}`}>
            {missing ? <ShieldAlert size={17} /> : <CheckCircle2 size={17} />}
            <span>{item.name}</span>
            <b>{item.status}</b>
          </div>
        );
      })}
    </div>
  );
}

function updatePricingItem(pricing, index, field, value) {
  return {
    ...pricing,
    items: (pricing.items || []).map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
  };
}

function PricingScheduleEditor({ packId, onSaved }) {
  const [pricingState, setPricingState] = useState({ loading: false, saving: false, pricing: null, error: "", message: "", files: [] });

  useEffect(() => {
    let cancelled = false;
    async function loadPricing() {
      if (!packId) {
        setPricingState({ loading: false, saving: false, pricing: null, error: "", message: "", files: [] });
        return;
      }
      setPricingState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
      const response = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/pricing`);
      if (cancelled) return;
      if (response.ok && response.data?.status === "ok") {
        setPricingState({ loading: false, saving: false, pricing: response.data.pricing, error: "", message: "", files: [] });
      } else {
        setPricingState({ loading: false, saving: false, pricing: null, error: response.error || "Pricing schedule could not be loaded.", message: "", files: [] });
      }
    }
    loadPricing();
    return () => {
      cancelled = true;
    };
  }, [packId]);

  const pricing = pricingState.pricing;
  const totals = pricing?.totals || {};

  function setPricing(pricingUpdate) {
    setPricingState((prev) => ({ ...prev, pricing: pricingUpdate, message: "", error: "" }));
  }

  async function recalculateDryRun() {
    if (!packId || !pricing) return;
    setPricingState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
    const response = await postEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/pricing/dry-run`, pricing);
    if (!response.ok || response.data?.status !== "ok") {
      setPricingState((prev) => ({ ...prev, loading: false, error: response.error || response.data?.message || "Dry-run recalculation failed." }));
      return;
    }
    setPricingState((prev) => ({ ...prev, loading: false, pricing: response.data.pricing, message: "Dry-run totals recalculated locally." }));
  }

  async function saveLocalPricing() {
    if (!packId || !pricing) return;
    setPricingState((prev) => ({ ...prev, saving: true, error: "", message: "" }));
    const response = await postEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/pricing/save-local`, pricing);
    if (!response.ok || response.data?.status !== "ok") {
      setPricingState((prev) => ({ ...prev, saving: false, error: response.error || response.data?.message || "Local pricing save failed." }));
      return;
    }
    setPricingState((prev) => ({
      ...prev,
      saving: false,
      pricing: response.data.pricing,
      files: response.data.files || [],
      message: "Local pricing schedule saved under runtime/quote_compilation.",
    }));
    onSaved?.(packId);
  }

  return (
    <div className="quote-pricing-editor">
      <div className="quote-pricing-head">
        <div>
          <h3>Pricing Schedule Completion</h3>
          <p>{pricingState.loading && !pricing ? "Loading local pricing model." : "Edit local pricing lines, then recalculate or save to the quote pack folder."}</p>
        </div>
        <div className="quote-pricing-safety">
          <span>LOCAL PRICING ONLY</span>
          <span>NOT SUBMITTED</span>
          <span>NOT EMAILED</span>
          <span>NOT UPLOADED</span>
        </div>
      </div>

      {pricingState.error ? <div className="quote-warning"><AlertTriangle size={16} />{pricingState.error}</div> : null}
      {pricingState.message ? <div className="quote-pricing-message">{pricingState.message}</div> : null}

      {pricing ? (
        <>
          <div className="quote-pricing-totals">
            <div><span>Subtotal ex VAT</span><b>{formatMoney(totals.subtotal_ex_vat)}</b></div>
            <div><span>VAT Total</span><b>{formatMoney(totals.vat_total)}</b></div>
            <div><span>Grand Total inc VAT</span><b>{formatMoney(totals.grand_total_inc_vat)}</b></div>
            <div><span>Estimated Profit</span><b>{formatMoney(totals.estimated_profit)}</b></div>
            <div><span>Margin</span><b>{Math.round(normalizeNumber(totals.margin_percent))}%</b></div>
          </div>

          <div className="quote-pricing-actions">
            <button type="button" disabled={pricingState.loading || pricingState.saving} onClick={recalculateDryRun}>Recalculate Dry Run</button>
            <button type="button" disabled={pricingState.loading || pricingState.saving} onClick={saveLocalPricing}>Save Local Pricing Schedule</button>
          </div>

          <div className="quote-pricing-table-scroll">
            <table className="quote-pricing-table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Description</th>
                  <th>Unit</th>
                  <th>Qty</th>
                  <th>Unit Cost</th>
                  <th>Markup %</th>
                  <th>Unit Price</th>
                  <th>Total ex VAT</th>
                  <th>VAT</th>
                  <th>Total inc VAT</th>
                  <th>Status</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {(pricing.items || []).map((item, index) => (
                  <tr key={`${item.line_no}-${index}`}>
                    <td>{item.line_no}</td>
                    <td><span className="quote-pricing-description">{item.description}</span></td>
                    <td>{item.unit}</td>
                    <td><input value={item.quantity ?? ""} onChange={(event) => setPricing(updatePricingItem(pricing, index, "quantity", event.target.value))} inputMode="decimal" /></td>
                    <td><input value={item.unit_cost ?? ""} onChange={(event) => setPricing(updatePricingItem(pricing, index, "unit_cost", event.target.value))} inputMode="decimal" /></td>
                    <td><input value={item.markup_percent ?? ""} onChange={(event) => setPricing(updatePricingItem(pricing, index, "markup_percent", event.target.value))} inputMode="decimal" /></td>
                    <td>{formatMoney(item.unit_price_ex_vat)}</td>
                    <td>{formatMoney(item.total_ex_vat)}</td>
                    <td>{formatMoney(item.vat_amount)}</td>
                    <td>{formatMoney(item.total_inc_vat)}</td>
                    <td>
                      <select value={safeText(item.pricing_status, "needs_review")} onChange={(event) => setPricing(updatePricingItem(pricing, index, "pricing_status", event.target.value))}>
                        <option value="needs_review">needs_review</option>
                        <option value="priced">priced</option>
                        <option value="operator_approved">operator_approved</option>
                      </select>
                    </td>
                    <td><input value={item.notes ?? ""} onChange={(event) => setPricing(updatePricingItem(pricing, index, "notes", event.target.value))} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="quote-pricing-alert-grid">
            <div>
              <h4>Missing Prices</h4>
              {(pricing.missing_prices || []).length ? pricing.missing_prices.map((item) => <p className="quote-risk missing" key={item}>{item}</p>) : <div className="quote-empty-inline">No missing prices after current calculation.</div>}
            </div>
            <div>
              <h4>Warnings</h4>
              {(pricing.warnings || []).length ? pricing.warnings.map((item) => <p className="quote-risk" key={item}>{item}</p>) : <div className="quote-empty-inline">No pricing warnings returned.</div>}
            </div>
            <div>
              <h4>Saved Files</h4>
              {pricingState.files.length ? (
                <ArtifactList items={pricingState.files.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))} empty="No saved pricing files yet." />
              ) : (
                <div className="quote-empty-inline">Save local pricing to create JSON and CSV files.</div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="quote-empty-inline">No pricing model is available for this pack yet.</div>
      )}
    </div>
  );
}

function FormalQuoteGenerator({ packId, onGenerated }) {
  const [formalState, setFormalState] = useState({ loading: false, generating: false, data: null, error: "", message: "" });

  useEffect(() => {
    let cancelled = false;
    async function loadFormalQuote() {
      if (!packId) {
        setFormalState({ loading: false, generating: false, data: null, error: "", message: "" });
        return;
      }
      setFormalState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
      const response = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/formal-quote`);
      if (cancelled) return;
      if (response.ok) {
        setFormalState({ loading: false, generating: false, data: response.data, error: "", message: response.data?.status === "ok" ? "" : safeText(response.data?.message) });
      } else {
        setFormalState({ loading: false, generating: false, data: null, error: response.error || "Formal quote status could not be loaded.", message: "" });
      }
    }
    loadFormalQuote();
    return () => {
      cancelled = true;
    };
  }, [packId]);

  async function generateFormalQuote() {
    if (!packId) return;
    setFormalState((prev) => ({ ...prev, generating: true, error: "", message: "" }));
    const response = await postEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/formal-quote/generate-local`, {});
    if (!response.ok || response.data?.status !== "ok") {
      setFormalState((prev) => ({
        ...prev,
        generating: false,
        error: response.error || response.data?.message || "Formal quote generation failed.",
        data: response.data || prev.data,
      }));
      return;
    }
    const detail = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/formal-quote`);
    const data = detail.ok ? detail.data : response.data;
    setFormalState({ loading: false, generating: false, data, error: "", message: "Formal quote generated locally." });
    onGenerated?.(packId);
  }

  const summary = formalState.data?.formal_quote_summary || {};
  const generatedFiles = asArray(formalState.data?.generated_files || summary.generated_files).map(normalizePackFile).filter(Boolean);
  const hasSummary = Boolean(summary.pack_id);

  return (
    <div className="quote-formal-quote">
      <div className="quote-formal-head">
        <div>
          <h3>Formal Quote Document Generation</h3>
          <p>{formalState.loading && !formalState.data ? "Checking local formal quote files." : hasSummary ? "Formal quote files are available for local operator review." : "Save pricing locally before generating the formal quote."}</p>
        </div>
        <div className="quote-formal-safety">
          <span>LOCAL QUOTE ONLY</span>
          <span>NOT SUBMITTED</span>
          <span>NOT EMAILED</span>
          <span>NOT UPLOADED</span>
        </div>
      </div>

      {formalState.error ? <div className="quote-warning"><AlertTriangle size={16} />{formalState.error}</div> : null}
      {formalState.message ? <div className="quote-pricing-message">{formalState.message}</div> : null}

      <div className="quote-formal-actions">
        <button type="button" disabled={formalState.loading || formalState.generating} onClick={generateFormalQuote}>
          {formalState.generating ? "Generating Formal Quote" : "Generate Formal Quote Locally"}
        </button>
      </div>

      {hasSummary ? (
        <>
          <div className="quote-formal-totals">
            <div><span>Total ex VAT</span><b>{formatMoney(summary.subtotal_ex_vat)}</b></div>
            <div><span>VAT</span><b>{formatMoney(summary.vat_total)}</b></div>
            <div><span>Total inc VAT</span><b>{formatMoney(summary.grand_total_inc_vat)}</b></div>
            <div><span>Estimated Profit</span><b>{formatMoney(summary.estimated_profit)}</b></div>
            <div><span>Margin</span><b>{Math.round(normalizeNumber(summary.margin_percent))}%</b></div>
          </div>
          <ArtifactList
            items={generatedFiles.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))}
            empty="No formal quote files were returned."
          />
        </>
      ) : (
        <div className="quote-empty-inline">No formal quote has been generated for this pack yet.</div>
      )}
    </div>
  );
}

function calculateReturnablesCompletion(review) {
  const rows = ["returnables", "sbd_forms", "company_documents"].flatMap((section) => asArray(review?.[section]));
  const required = rows.filter((row) => row?.required !== false);
  const completedCount = required.filter((row) => ["completed", "not_applicable"].includes(safeText(row.status))).length;
  const missingCount = required.filter((row) => safeText(row.status) === "missing").length;
  const needsReviewCount = required.filter((row) => safeText(row.status) === "needs_review").length;
  return {
    required_count: required.length,
    completed_count: completedCount,
    missing_count: missingCount,
    needs_review_count: needsReviewCount,
    completion_score: required.length ? Math.round((completedCount / required.length) * 100) : 100,
  };
}

function withReturnablesCompletion(review) {
  return { ...review, completion: calculateReturnablesCompletion(review) };
}

function updateReturnablesItem(review, section, index, field, value) {
  return withReturnablesCompletion({
    ...review,
    [section]: asArray(review?.[section]).map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)),
  });
}

function ReturnablesSectionTable({ title, section, rows, labelKey, onChange }) {
  return (
    <div className="quote-returnables-table-card">
      <h4>{title}</h4>
      <div className="quote-returnables-table-scroll">
        <table className="quote-returnables-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Required</th>
              <th>Status</th>
              <th>Source File</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item, index) => (
              <tr key={`${section}-${item.id || item.form || item.name}-${index}`}>
                <td><span>{item[labelKey]}</span><small>{item.category || section}</small></td>
                <td>{item.required === false ? "No" : "Yes"}</td>
                <td>
                  <select value={safeText(item.status, "missing")} onChange={(event) => onChange(section, index, "status", event.target.value)}>
                    {RETURNABLE_STATUS_OPTIONS.map((status) => <option value={status} key={status}>{status}</option>)}
                  </select>
                </td>
                <td><input value={item.source_file || ""} onChange={(event) => onChange(section, index, "source_file", event.target.value)} placeholder="Local file path or note" /></td>
                <td><input value={item.notes || ""} onChange={(event) => onChange(section, index, "notes", event.target.value)} placeholder="Operator notes" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReturnablesCompletionEditor({ packId, onSaved }) {
  const [returnablesState, setReturnablesState] = useState({ loading: false, saving: false, review: null, error: "", message: "", files: [] });

  useEffect(() => {
    let cancelled = false;
    async function loadReturnables() {
      if (!packId) {
        setReturnablesState({ loading: false, saving: false, review: null, error: "", message: "", files: [] });
        return;
      }
      setReturnablesState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
      const response = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/returnables`);
      if (cancelled) return;
      if (response.ok && response.data?.status === "ok") {
        setReturnablesState({ loading: false, saving: false, review: withReturnablesCompletion(response.data.returnables_review), error: "", message: "", files: response.data.files || [] });
      } else {
        setReturnablesState({ loading: false, saving: false, review: null, error: response.error || response.data?.message || "Returnables review could not be loaded.", message: "", files: [] });
      }
    }
    loadReturnables();
    return () => {
      cancelled = true;
    };
  }, [packId]);

  const review = returnablesState.review;
  const completion = review?.completion || {};

  function editItem(section, index, field, value) {
    setReturnablesState((prev) => ({
      ...prev,
      review: updateReturnablesItem(prev.review, section, index, field, value),
      message: "",
      error: "",
    }));
  }

  async function saveLocalReturnables() {
    if (!packId || !review) return;
    setReturnablesState((prev) => ({ ...prev, saving: true, error: "", message: "" }));
    const response = await postEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/returnables/save-local`, review);
    if (!response.ok || response.data?.status !== "ok") {
      setReturnablesState((prev) => ({ ...prev, saving: false, error: response.error || response.data?.message || "Local returnables save failed." }));
      return;
    }
    setReturnablesState((prev) => ({
      ...prev,
      saving: false,
      review: withReturnablesCompletion(response.data.returnables_review),
      files: response.data.files || [],
      message: "Local returnables review saved under runtime/quote_compilation.",
    }));
    onSaved?.(packId);
  }

  return (
    <div className="quote-returnables-editor">
      <div className="quote-returnables-head">
        <div>
          <h3>Returnables & SBD Completion</h3>
          <p>{returnablesState.loading && !review ? "Loading local returnables checklist." : "Track returnables, SBD forms, and company documents for operator review only."}</p>
        </div>
        <div className="quote-returnables-safety">
          <span>LOCAL RETURNABLES REVIEW ONLY</span>
          <span>NOT SUBMITTED</span>
          <span>NOT EMAILED</span>
          <span>NOT UPLOADED</span>
        </div>
      </div>

      {returnablesState.error ? <div className="quote-warning"><AlertTriangle size={16} />{returnablesState.error}</div> : null}
      {returnablesState.message ? <div className="quote-pricing-message">{returnablesState.message}</div> : null}

      {review ? (
        <>
          <div className="quote-returnables-score-grid">
            <div><span>Completion Score</span><b>{completion.completion_score ?? 0}%</b></div>
            <div><span>Required</span><b>{completion.required_count ?? 0}</b></div>
            <div><span>Completed</span><b>{completion.completed_count ?? 0}</b></div>
            <div><span>Missing</span><b>{completion.missing_count ?? 0}</b></div>
            <div><span>Needs Review</span><b>{completion.needs_review_count ?? 0}</b></div>
          </div>

          <div className="quote-returnables-actions">
            <button type="button" disabled={returnablesState.loading || returnablesState.saving} onClick={saveLocalReturnables}>
              {returnablesState.saving ? "Saving Local Returnables Review" : "Save Local Returnables Review"}
            </button>
          </div>

          <ReturnablesSectionTable title="Returnables" section="returnables" rows={asArray(review.returnables)} labelKey="name" onChange={editItem} />
          <ReturnablesSectionTable title="SBD Forms" section="sbd_forms" rows={asArray(review.sbd_forms)} labelKey="form" onChange={editItem} />
          <ReturnablesSectionTable title="Company Documents" section="company_documents" rows={asArray(review.company_documents)} labelKey="name" onChange={editItem} />

          {returnablesState.files.length ? (
            <ArtifactList items={returnablesState.files.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))} empty="No saved returnables files yet." />
          ) : null}
        </>
      ) : (
        <div className="quote-empty-inline">No returnables review model is available for this pack yet.</div>
      )}
    </div>
  );
}

function SubmissionBinderPanel({ packId, onGenerated }) {
  const [binderState, setBinderState] = useState({ loading: false, generating: false, data: null, error: "", message: "", reviewState: "" });

  useEffect(() => {
    let cancelled = false;
    async function loadBinder() {
      if (!packId) {
        setBinderState({ loading: false, generating: false, data: null, error: "", message: "", reviewState: "" });
        return;
      }
      setBinderState((prev) => ({ ...prev, loading: true, error: "", message: "" }));
      const response = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/submission-binder`);
      if (cancelled) return;
      if (response.ok) {
        setBinderState((prev) => ({
          ...prev,
          loading: false,
          data: response.data,
          error: "",
          message: response.data?.status === "ok" ? "" : safeText(response.data?.message),
        }));
      } else {
        setBinderState((prev) => ({ ...prev, loading: false, data: null, error: response.error || "Submission binder status could not be loaded.", message: "" }));
      }
    }
    loadBinder();
    return () => {
      cancelled = true;
    };
  }, [packId]);

  async function generateBinder() {
    if (!packId) return;
    setBinderState((prev) => ({ ...prev, generating: true, error: "", message: "" }));
    const response = await postEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/submission-binder/generate-local`, {});
    if (!response.ok || response.data?.status !== "ok") {
      setBinderState((prev) => ({
        ...prev,
        generating: false,
        error: response.error || response.data?.message || "Submission binder generation failed.",
        data: response.data || prev.data,
      }));
      return;
    }
    const detail = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}/submission-binder`);
    const data = detail.ok ? detail.data : response.data;
    setBinderState((prev) => ({ ...prev, loading: false, generating: false, data, error: "", message: "Local submission binder generated." }));
    onGenerated?.(packId);
  }

  const manifest = binderState.data?.submission_binder_manifest || {};
  const readiness = binderState.data?.readiness?.readiness || binderState.data?.readiness || manifest.readiness || {};
  const binderFiles = asArray(binderState.data?.binder_files || manifest.binder_files).map(normalizePackFile).filter(Boolean);
  const sourceFiles = asArray(binderState.data?.source_files || manifest.source_files).map(normalizePackFile).filter(Boolean);
  const hasBinder = Boolean(manifest.pack_id || binderFiles.length);

  return (
    <div className="quote-binder-panel">
      <div className="quote-binder-head">
        <div>
          <h3>Submission Pack Readiness Binder</h3>
          <p>{binderState.loading && !binderState.data ? "Checking local submission binder files." : hasBinder ? "Local submission binder is available for Submission Centre review." : "Generate a local binder to consolidate pack readiness."}</p>
        </div>
        <div className="quote-binder-safety">
          <span>LOCAL SUBMISSION BINDER ONLY</span>
          <span>NOT SUBMITTED</span>
          <span>NOT EMAILED</span>
          <span>NOT UPLOADED</span>
          <span>FINAL SUBMIT LOCKED</span>
        </div>
      </div>

      {binderState.error ? <div className="quote-warning"><AlertTriangle size={16} />{binderState.error}</div> : null}
      {binderState.message ? <div className="quote-pricing-message">{binderState.message}</div> : null}

      <div className="quote-binder-actions">
        <button type="button" disabled={binderState.loading || binderState.generating} onClick={generateBinder}>
          {binderState.generating ? "Generating Local Submission Binder" : "Generate Local Submission Binder"}
        </button>
        {["Binder Reviewed Locally", "Needs Pricing Fix", "Needs Returnables Fix", "Ready for Submission Centre Review"].map((action) => (
          <button type="button" key={action} onClick={() => setBinderState((prev) => ({ ...prev, reviewState: action }))}>
            {action}
          </button>
        ))}
      </div>
      {binderState.reviewState ? <div className="quote-local-state">Local binder review state: {binderState.reviewState}</div> : null}

      <div className="quote-binder-score-grid">
        <div><span>Binder Score</span><b>{normalizeScore(readiness.submission_binder_score, 0)}%</b></div>
        <div><span>Pricing</span><b>{readiness.pricing_completed ? "Complete" : "Missing"}</b></div>
        <div><span>Formal Quote</span><b>{readiness.formal_quote_generated ? "Generated" : "Missing"}</b></div>
        <div><span>Returnables</span><b>{readiness.returnables_review_completed ? "Reviewed" : "Missing"}</b></div>
      </div>

      <div className="quote-binder-grid">
        <div>
          <h4>Missing Items</h4>
          {asArray(readiness.missing_items).length ? asArray(readiness.missing_items).map((item) => <p className="quote-risk missing" key={item}>{item}</p>) : <div className="quote-empty-inline">No binder missing items recorded.</div>}
        </div>
        <div>
          <h4>Blockers</h4>
          {asArray(readiness.blockers).length ? asArray(readiness.blockers).map((item) => <p className="quote-risk" key={item}>{item}</p>) : <div className="quote-empty-inline">No binder blockers detected.</div>}
        </div>
      </div>

      <div className="quote-binder-files-grid">
        <div>
          <h4>Binder Files</h4>
          <ArtifactList items={binderFiles.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))} empty="No binder files generated yet." />
        </div>
        <div>
          <h4>Source Files</h4>
          <ArtifactList items={sourceFiles.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))} empty="No local source files detected for binder readiness." />
        </div>
      </div>
    </div>
  );
}

function DetailDrawer({ pack, activeTab, setActiveTab, onClose, operatorState, onOperatorAction, onGenerateLocalPack, generationLoading }) {
  if (!pack) return null;
  const urgency = urgencyMeta(pack.closing_date);
  const localDecision = operatorState[pack.id];

  return (
    <div className="quote-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="quote-drawer" aria-label="Quote pack detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="quote-drawer-head">
          <div>
            <span className="quote-kicker">{pack.rfq_reference}</span>
            <h2>{pack.title}</h2>
            <p>{pack.buyer} · {pack.province} · {formatDate(pack.closing_date)}</p>
          </div>
          <button className="quote-icon-button" type="button" onClick={onClose} aria-label="Close quote pack detail">
            <X size={18} />
          </button>
        </div>

        <div className="quote-drawer-scorebar">
          <ScoreChip label="Quote Readiness" score={pack.quote_readiness_score} />
          <StatusChip label="Pricing" status={pack.pricing_schedule_status} />
          <StatusChip label="BOQ" status={pack.boq_status} />
          <span className={`quote-urgency ${urgency.tone}`}><Clock3 size={14} />{urgency.label}</span>
        </div>

        <div className="quote-operator-actions">
          <button type="button" onClick={() => onOperatorAction(pack.id, "Ready for Pricing")}><FileSpreadsheet size={15} />Mark Ready for Pricing</button>
          <button type="button" onClick={() => onOperatorAction(pack.id, "Held for Missing Docs")}><PauseCircle size={15} />Hold for Missing Docs</button>
          <button type="button" onClick={() => onOperatorAction(pack.id, "Approved Quote Pack Prep")}><ThumbsUp size={15} />Approve Quote Pack Prep</button>
          <button type="button" onClick={() => onOperatorAction(pack.id, "Rejected Quote Pack")}><Ban size={15} />Reject Quote Pack</button>
          <button type="button" className="quote-local-generate-button" disabled={generationLoading || pack._demo} onClick={() => onGenerateLocalPack(pack)}><PackageCheck size={15} />Generate Local Quote Pack</button>
        </div>
        {localDecision ? <div className="quote-local-state">Local operator state: {localDecision}</div> : null}

        <div className="quote-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="quote-drawer-body">
          {activeTab === "Overview" ? (
            <div className="quote-detail-grid">
              <div className="quote-detail-card"><span>Quote Status</span><b>{pack.quote_status}</b></div>
              <div className="quote-detail-card"><span>Estimated Value</span><b>{formatMoney(pack.estimated_value)}</b></div>
              <div className="quote-detail-card"><span>Estimated Profit</span><b>{formatMoney(pack.estimated_profit)}</b></div>
              <div className="quote-detail-card"><span>Margin</span><b>{Math.round(pack.margin_percent || 0)}%</b></div>
              <div className="quote-detail-wide">
                <h3>Recommended Next Step</h3>
                <p>{pack.recommended_next_step}</p>
              </div>
            </div>
          ) : null}

          {activeTab === "Pricing Schedule" ? <ArtifactList items={pack.pricing_schedules} empty="No pricing schedule detected." /> : null}
          {activeTab === "BOQ" ? <ArtifactList items={pack.boqs} empty="No BOQ detected." /> : null}
          {activeTab === "Returnables" ? <Checklist items={pack.returnables} missingItems={pack.missing_items} /> : null}
          {activeTab === "Generated Files" ? <ArtifactList items={pack.generated_files} empty="No generated quote-pack files detected." /> : null}
          {activeTab === "Risks" ? (
            <div className="quote-risk-list">
              {pack.risks.length ? pack.risks.map((risk, index) => <p className="quote-risk" key={`risk-${risk}-${index}`}>{risk}</p>) : <div className="quote-empty-inline">No quote-pack risks detected.</div>}
              {pack.missing_items.length ? (
                <>
                  <h3 className="quote-section-title">Missing Items</h3>
                  {pack.missing_items.map((item, index) => <p className="quote-risk" key={`missing-${item}-${index}`}>{item}</p>)}
                </>
              ) : null}
            </div>
          ) : null}

          <p className="quote-safety-note">LOCAL ONLY. NOT SUBMITTED. NOT EMAILED. NOT UPLOADED. No final submit, portal upload, email, or CAPTCHA action is exposed.</p>
        </div>
      </aside>
    </div>
  );
}

function QuotePackQualityReview({ packDetail, loading, error, reviewState, onReviewAction, onPricingSaved }) {
  const manifest = packDetail?.manifest || {};
  const metadata = packDetail?.metadata || {};
  const readiness = manifest.readiness || {};
  const pricingReview = packDetail?.pricing_schedule_review || {};
  const checklist = packDetail?.returnables_checklist || {};
  const files = getPackFiles(packDetail);
  const missingItems = getPackMissingItems(packDetail);
  const packId = safeText(packDetail?.pack_id || metadata.pack_id || manifest.pack_id);
  const localReview = packId ? reviewState[packId] : "";

  return (
    <section className="quote-quality-review card">
      <div className="quote-quality-head">
        <div>
          <p className="eyebrow">Quote Pack Quality Review</p>
          <h2>Latest Generated Pack</h2>
          <p>{loading ? "Checking local quote compilation runtime." : packId ? "Read-only review data loaded from runtime/quote_compilation." : "No local quote pack has been generated yet."}</p>
        </div>
        <div className="quote-quality-safety">
          <span>LOCAL PACK ONLY</span>
          <span>NOT SUBMITTED</span>
          <span>NOT EMAILED</span>
          <span>NOT UPLOADED</span>
        </div>
      </div>

      {error ? <div className="quote-warning"><AlertTriangle size={16} />{error}</div> : null}

      {packId ? (
        <>
          <div className="quote-quality-summary">
            <div><span>Pack ID</span><b>{packId}</b></div>
            <div><span>RFQ</span><b>{metadata.rfq_reference || manifest.rfq_reference || "Unknown RFQ"}</b></div>
            <div><span>Buyer</span><b>{metadata.buyer || manifest.buyer || "Unknown Buyer"}</b></div>
            <div><span>Readiness</span><b>{normalizeScore(readiness.quote_readiness_score, 0)}</b></div>
          </div>

          <div className="quote-quality-actions">
            {["Mark Reviewed Locally", "Needs Pricing Fix", "Needs Documents", "Ready for Operator Approval"].map((action) => (
              <button key={action} type="button" onClick={() => onReviewAction(packId, action)}>
                {action}
              </button>
            ))}
          </div>
          {localReview ? <div className="quote-local-state">Local quality review state: {localReview}</div> : null}

          <div className="quote-quality-grid">
            <div className="quote-quality-card">
              <h3>Manifest Preview</h3>
              <div className="quote-manifest-preview">
                <span>Created</span><b>{safeText(manifest.created_at || metadata.created_at, "Unknown")}</b>
                <span>Title</span><b>{manifest.title || metadata.title || "Untitled pack"}</b>
                <span>Files</span><b>{files.length}</b>
              </div>
            </div>

            <div className="quote-quality-card">
              <h3>Missing Items</h3>
              {missingItems.length ? missingItems.map((item) => <p className="quote-risk missing" key={`missing-${item}`}>{item}</p>) : <div className="quote-empty-inline">No missing items recorded in the manifest.</div>}
            </div>

            <div className="quote-quality-card">
              <h3>Pricing Schedule Review</h3>
              <div className="quote-quality-flags">
                <StatusChip label="Pricing" status={pricingReview.pricing_schedule_found ? "Ready" : "Missing"} />
                <StatusChip label="BOQ" status={pricingReview.boq_found ? "Ready" : "Missing"} />
              </div>
              <ArtifactList items={asArray(pricingReview.pricing_schedules).map((item) => normalizeArtifact(item, "Pricing Schedule")).filter(Boolean)} empty="No pricing schedule file listed in the review." />
            </div>

            <div className="quote-quality-card">
              <h3>Returnables Checklist</h3>
              <div className="quote-quality-flags">
                <StatusChip label="Buyer Forms" status={checklist.buyer_forms_found ? "Ready" : "Missing"} />
                <StatusChip label="SBD" status={checklist.sbd_forms_found ? "Ready" : "Missing"} />
              </div>
              <Checklist
                items={asArray(checklist.sbd_forms).map((item) => ({ name: safeText(item.name || item.path || item, "SBD form"), status: "Ready" }))}
                missingItems={missingItems}
              />
            </div>

            <div className="quote-quality-card">
              <h3>Generated Files</h3>
              <ArtifactList items={files.map((file) => ({ name: file.name, type: file.type, url: file.url, status: file.size_bytes ? `${file.size_bytes} bytes` : "" }))} empty="No generated files found for this pack." />
            </div>

            <div className="quote-quality-card">
              <h3>Operator Next Steps</h3>
              {safeText(packDetail?.operator_next_steps) ? <pre className="quote-next-steps">{packDetail.operator_next_steps}</pre> : <div className="quote-empty-inline">No operator next steps text found.</div>}
            </div>
          </div>

          <ReturnablesCompletionEditor packId={packId} onSaved={onPricingSaved} />
          <PricingScheduleEditor packId={packId} onSaved={onPricingSaved} />
          <FormalQuoteGenerator packId={packId} onGenerated={onPricingSaved} />
          <SubmissionBinderPanel packId={packId} onGenerated={onPricingSaved} />
        </>
      ) : (
        <div className="quote-empty-inline">Generate a local quote pack to populate the quality review layer.</div>
      )}
    </section>
  );
}

function PanelShell({ title, icon: Icon, children }) {
  return (
    <div className="quote-panel card">
      <div className="quote-panel-head">
        <h3>{Icon ? <Icon size={16} /> : null}{title}</h3>
      </div>
      {children}
    </div>
  );
}

export default function QuotePackEngineWorkspace() {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], error: "" });
  const [packs, setPacks] = useState([]);
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [quoteStatus, setQuoteStatus] = useState("All");
  const [readiness, setReadiness] = useState("All");
  const [urgency, setUrgency] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});
  const [compilationState, setCompilationState] = useState({ loading: false, result: null, error: "" });
  const [qualityState, setQualityState] = useState({ loading: true, latest: null, error: "" });
  const [qualityReviewState, setQualityReviewState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadQuotePacks() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(QUOTE_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeQuotePackRecord(record, record._sourcePath));

      const merged = mergeQuotePacks(records).filter((pack) => pack.rfq_reference !== "RFQ" || pack.title !== "RFQ");
      setPacks(merged.length ? merged : DEMO_QUOTE_PACKS);
      setEndpointState({
        loading: false,
        results,
        error: results.some((result) => result.ok) ? "" : "No quote-pack endpoints responded with usable data.",
      });
    }

    async function loadLatestPack() {
      setQualityState((prev) => ({ ...prev, loading: true, error: "" }));
      const result = await fetchEndpoint(QUOTE_PACK_LATEST_ENDPOINT);
      if (cancelled) return;
      if (result.ok && result.data?.status === "ok") {
        setQualityState({ loading: false, latest: result.data, error: "" });
      } else {
        setQualityState({ loading: false, latest: null, error: "" });
      }
    }

    loadQuotePacks();
    loadLatestPack();
    return () => {
      cancelled = true;
    };
  }, []);

  const quoteStatuses = useMemo(() => ["All", ...uniqueBy(packs.map((pack) => pack.quote_status), (item) => item).filter(Boolean)], [packs]);
  const selectedPack = useMemo(() => packs.find((pack) => pack.id === selectedId), [packs, selectedId]);

  const filteredPacks = useMemo(() => {
    const term = query.trim().toLowerCase();
    return packs.filter((pack) => {
      const haystack = `${pack.rfq_reference} ${pack.title} ${pack.buyer} ${pack.quote_status}`.toLowerCase();
      const readinessMatch =
        readiness === "All" ||
        (readiness === "Ready >=80" && pack.quote_readiness_score >= 80) ||
        (readiness === "Review 50-79" && pack.quote_readiness_score >= 50 && pack.quote_readiness_score < 80) ||
        (readiness === "Blocked <50" && pack.quote_readiness_score < 50) ||
        (readiness === "Missing Items" && pack.missing_items.length > 0);
      const urgencyDays = daysUntil(pack.closing_date);
      const urgencyMatch =
        urgency === "All" ||
        (urgency === "Overdue" && urgencyDays < 0) ||
        (urgency === "0-2 Days" && urgencyDays >= 0 && urgencyDays <= 2) ||
        (urgency === "3-7 Days" && urgencyDays >= 3 && urgencyDays <= 7) ||
        (urgency === "8+ Days" && urgencyDays > 7);
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || pack.province === province) &&
        (quoteStatus === "All" || pack.quote_status === quoteStatus) &&
        readinessMatch &&
        urgencyMatch
      );
    });
  }, [packs, province, query, quoteStatus, readiness, urgency]);

  const summary = useMemo(() => ({
    total: packs.length,
    ready: packs.filter((pack) => pack.quote_readiness_score >= 80).length,
    pricingReady: packs.filter((pack) => pack.pricing_schedule_status === "Ready").length,
    missing: packs.filter((pack) => pack.missing_items.length > 0).length,
  }), [packs]);

  const focusedPack = selectedPack || filteredPacks[0] || packs[0] || DEMO_QUOTE_PACKS[0];
  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = packs.some((pack) => pack._demo);
  const qualityPackDetail = qualityState.latest || packDetailFromGeneration(compilationState.result);

  function openPack(pack) {
    setSelectedId(pack.id);
    setActiveTab("Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  async function generateLocalQuotePack(pack) {
    if (!pack || pack._demo) {
      setCompilationState({ loading: false, result: null, error: "Local generation needs a live RFQ candidate." });
      return;
    }
    setCompilationState({ loading: true, result: null, error: "" });
    const response = await postEndpoint("/quote-compilation/generate-local-pack", {
      id: pack.id,
      rfq_reference: pack.rfq_reference,
      title: pack.title,
    });
    if (!response.ok) {
      setCompilationState({ loading: false, result: null, error: response.error });
      return;
    }
    const generatedPackId = response.data?.manifest?.pack_id;
    let latestDetail = generatedPackId ? packDetailFromGeneration(response.data) : null;
    if (generatedPackId) {
      setQualityState((prev) => ({ ...prev, loading: true, error: "" }));
      const detailResponse = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(generatedPackId)}`);
      if (detailResponse.ok && detailResponse.data?.status === "ok") {
        latestDetail = detailResponse.data;
      }
    }
    setCompilationState({ loading: false, result: response.data, error: "" });
    if (latestDetail) {
      setQualityState({ loading: false, latest: latestDetail, error: "" });
    } else {
      setQualityState((prev) => ({ ...prev, loading: false }));
    }
    setOperatorState((prev) => ({ ...prev, [pack.id]: "Local Quote Pack Generated" }));
  }

  function setQualityReviewAction(packId, action) {
    setQualityReviewState((prev) => ({ ...prev, [packId]: action }));
  }

  async function refreshQualityPack(packId) {
    if (!packId) return;
    setQualityState((prev) => ({ ...prev, loading: true, error: "" }));
    const detailResponse = await fetchEndpoint(`/quote-compilation/packs/${encodeURIComponent(packId)}`);
    if (detailResponse.ok && detailResponse.data?.status === "ok") {
      setQualityState({ loading: false, latest: detailResponse.data, error: "" });
    } else {
      setQualityState((prev) => ({ ...prev, loading: false, error: detailResponse.error || "Latest quote pack refresh failed." }));
    }
  }

  return (
    <section className="quote-pack-workspace" id="quote-pack-engine">
      <div className="quote-pack-hero card">
        <div>
          <p className="eyebrow">Quote Pack Engine</p>
          <h1>Quote Pack Engine Workspace</h1>
          <p className="muted">Read-only pack preparation view probing {API_BASE}. Local pack generation writes only to backend runtime storage.</p>
        </div>
        <div className="quote-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${QUOTE_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="quote-local-safety-strip card">
        <span>LOCAL ONLY</span>
        <span>NOT SUBMITTED</span>
        <span>NOT EMAILED</span>
        <span>NOT UPLOADED</span>
      </div>

      <div className="quote-summary-grid">
        <div className="quote-summary-card"><span>Quote Packs</span><b>{summary.total}</b></div>
        <div className="quote-summary-card good"><span>Ready</span><b>{summary.ready}</b></div>
        <div className="quote-summary-card blue"><span>Pricing Ready</span><b>{summary.pricingReady}</b></div>
        <div className="quote-summary-card amber"><span>Missing Items</span><b>{summary.missing}</b></div>
      </div>

      <div className="quote-toolbar card">
        <label className="quote-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search RFQ, buyer, status" />
        </label>
        <label>
          <Filter size={15} />
          <select value={province} onChange={(event) => setProvince(event.target.value)}>
            {PROVINCES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <Filter size={15} />
          <select value={quoteStatus} onChange={(event) => setQuoteStatus(event.target.value)}>
            {quoteStatuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <Filter size={15} />
          <select value={readiness} onChange={(event) => setReadiness(event.target.value)}>
            {["All", "Ready >=80", "Review 50-79", "Blocked <50", "Missing Items"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          <Filter size={15} />
          <select value={urgency} onChange={(event) => setUrgency(event.target.value)}>
            {["All", "Overdue", "0-2 Days", "3-7 Days", "8+ Days"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>

      {endpointState.error ? <div className="quote-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="quote-warning"><PackageCheck size={16} />No live quote-pack rows were found. Showing a non-destructive workspace preview row.</div> : null}
      {compilationState.error ? <div className="quote-warning"><AlertTriangle size={16} />{compilationState.error}</div> : null}
      {compilationState.result?.manifest ? (
        <div className="quote-generated-manifest card">
          <div>
            <span>Generated Local Manifest</span>
            <b>{compilationState.result.manifest.pack_id}</b>
            <p>{compilationState.result.workspace}</p>
          </div>
          <div className="quote-manifest-files">
            {(compilationState.result.manifest.files || []).map((file) => (
              <span key={file.path || file.name}>{file.name}</span>
            ))}
          </div>
        </div>
      ) : null}

      <QuotePackQualityReview
        packDetail={qualityPackDetail}
        loading={qualityState.loading}
        error={qualityState.error}
        reviewState={qualityReviewState}
        onReviewAction={setQualityReviewAction}
        onPricingSaved={refreshQualityPack}
      />

      <div className="quote-table-card card">
        <div className="card-head">
          <h2>RFQ Quote Queue</h2>
          <span>{filteredPacks.length} visible</span>
        </div>
        <div className="quote-table-scroll">
          <table className="quote-table">
            <thead>
              <tr>
                <th>RFQ</th>
                <th>Buyer</th>
                <th>Province</th>
                <th>Quote Status</th>
                <th>Readiness</th>
                <th>Pricing</th>
                <th>BOQ</th>
                <th>Closing</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredPacks.map((pack, index) => {
                const close = urgencyMeta(pack.closing_date);
                return (
                  <tr key={`${pack.id}-${index}`} onClick={() => openPack(pack)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && openPack(pack)}>
                    <td>
                      <b>{pack.rfq_reference}</b>
                      <span>{pack.title}</span>
                    </td>
                    <td>{pack.buyer}</td>
                    <td>{pack.province}</td>
                    <td><span className="pill">{operatorState[pack.id] || pack.quote_status}</span></td>
                    <td><ScoreChip label="Score" score={pack.quote_readiness_score} /></td>
                    <td><StatusChip label="" status={pack.pricing_schedule_status} /></td>
                    <td><StatusChip label="" status={pack.boq_status} /></td>
                    <td><span className={`quote-urgency ${close.tone}`}><Clock3 size={14} />{close.label}</span></td>
                    <td><button type="button" className="quote-row-button" onClick={(event) => { event.stopPropagation(); openPack(pack); }}>Open</button></td>
                  </tr>
                );
              })}
              {!filteredPacks.length ? (
                <tr>
                  <td colSpan="9">
                    <div className="quote-empty-inline">No quote packs match the current filters.</div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="quote-pack-panels">
        <PanelShell title="Pricing Schedule Panel" icon={FileSpreadsheet}>
          <div className="quote-panel-status"><StatusChip label="Pricing" status={focusedPack.pricing_schedule_status} /></div>
          <ArtifactList items={focusedPack.pricing_schedules} empty="No pricing schedule detected for the focused RFQ." />
        </PanelShell>

        <PanelShell title="BOQ Readiness Panel" icon={Layers3}>
          <div className="quote-panel-status"><StatusChip label="BOQ" status={focusedPack.boq_status} /></div>
          <ArtifactList items={focusedPack.boqs} empty="No BOQ detected for the focused RFQ." />
        </PanelShell>

        <PanelShell title="Returnables / SBD Checklist" icon={FileCheck2}>
          <div className="quote-panel-status">
            <StatusChip label="SBD" status={focusedPack.sbd_status} />
            <StatusChip label="Returnables" status={focusedPack.returnables_status} />
          </div>
          <Checklist items={focusedPack.returnables} missingItems={focusedPack.missing_items} />
        </PanelShell>

        <PanelShell title="Generated Files / Pack Preview" icon={FileArchive}>
          <div className="quote-local-generation-panel">
            <button type="button" disabled={compilationState.loading || focusedPack._demo} onClick={() => generateLocalQuotePack(focusedPack)}>
              <PackageCheck size={15} />
              {compilationState.loading ? "Generating Local Pack" : "Generate Local Quote Pack"}
            </button>
            <span>LOCAL ONLY · NOT SUBMITTED · NOT EMAILED · NOT UPLOADED</span>
          </div>
          <ArtifactList items={focusedPack.generated_files} empty="No generated quote-pack files detected for the focused RFQ." />
        </PanelShell>

        <PanelShell title="Risk & Missing Items Panel" icon={AlertTriangle}>
          <div className="quote-risk-list">
            {(focusedPack.risks.length ? focusedPack.risks : ["No quote-pack risks detected."]).map((risk, index) => <p className="quote-risk" key={`panel-risk-${risk}-${index}`}>{risk}</p>)}
            {focusedPack.missing_items.map((item, index) => <p className="quote-risk missing" key={`panel-missing-${item}-${index}`}>{item}</p>)}
          </div>
        </PanelShell>
      </div>

      <DetailDrawer
        pack={selectedPack}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
        onGenerateLocalPack={generateLocalQuotePack}
        generationLoading={compilationState.loading}
      />
    </section>
  );
}
