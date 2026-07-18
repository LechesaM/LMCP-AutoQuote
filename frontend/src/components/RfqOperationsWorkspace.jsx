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
  "/rfq-lifecycle/live-rfqs",
  "/supply-command/live-rfqs",
  "/tender-pipeline/live-rfqs",
];

const HISTORICAL_ENDPOINTS = [
  "/rfq-lifecycle/historical-rfqs",
];

const CLASSIFICATION_REVIEW_ENDPOINTS = [
  "/rfq-lifecycle/review-required-rfqs",
];

const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
const DRAWER_TABS = ["Overview", "Documents", "BOQ / Pricing", "Supplier Validation", "Qualification", "Submission Readiness", "Proofs / Audit"];

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
  const identity = pick(record, ["id", "rfq_id", "canonical_rfq_id", "reference", "rfq_reference", "rfq_number", "buyer_rfq_number", "reference_number", "title", "description"]);
  return Boolean(identity) && /(rfq|tender|opportunit|buyer|closing|quote|submission|boq|pricing|document|reference|title|description)/.test(keys);
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
  const explicit = asArray(pick(record, ["risks", "risk_flags", "alerts", "warnings", "blockers"])).map((item) => safeText(item)).filter(Boolean);
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
  const missingReturnables = uniqueBy(
    asArray(pick(record, ["missing_returnables", "missing_documents", "missing_forms", "returnables_missing", "upload_missing", "readiness_gaps"]))
      .map((item) => safeText(typeof item === "object" ? pick(item, ["name", "label", "field", "document", "reason"]) : item))
      .filter(Boolean),
    (item) => item.toLowerCase(),
  );
  const estimatedValue = normalizeNumber(pick(record, ["estimated_value", "value", "contract_value", "budget", "amount"]));
  const estimatedProfit = normalizeNumber(pick(record, ["estimated_profit", "profit", "total_profit", "gross_profit"]));
  const marginPercent = normalizeNumber(pick(record, ["margin_percent", "margin", "profit_margin"]), estimatedValue ? (estimatedProfit / estimatedValue) * 100 : 0);
  const scores = deriveScores(record, missingReturnables, boqs, pricingSchedules, allDocuments);
  const risks = normalizeRisks(record, missingReturnables, boqs, pricingSchedules);
  const id = slug(pick(record, ["id", "rfq_id"], "") || `${reference}-${title}`) || crypto.randomUUID();
  const status = normalizeStatus(pick(record, ["status", "lifecycle_state", "pipeline_status", "stage", "submission_status"]), record);
  const recommendedAction =
    safeText(pick(record, ["recommended_action", "next_action", "operator_action"])) ||
    (scores.submission >= 80 ? "Approve for quote prep" : risks.length ? "Mark for review" : "Continue qualification");

  return {
    id,
    reference,
    title,
    buyer,
    province,
    closing_date: safeText(pick(record, ["closing_date", "closing", "close_date", "deadline", "closing_datetime"])),
    source: safeText(pick(record, ["source", "portal", "origin"]), sourcePath),
    status,
    estimated_value: estimatedValue,
    estimated_profit: estimatedProfit,
    margin_percent: marginPercent,
    documents: allDocuments,
    boqs,
    pricing_schedules: pricingSchedules,
    missing_returnables: missingReturnables,
    qualification_score: scores.qualification,
    quote_readiness_score: scores.quote,
    submission_readiness_score: scores.submission,
    risks,
    recommended_action: recommendedAction,
    proofs: collectArtifacts(record, ["proofs", "submission_proofs", "proof_files", "receipts"], "Proof"),
    audit: asArray(pick(record, ["audit", "events", "history", "timeline"])).filter((item) => item && typeof item === "object").slice(0, 8),
    operational_classification: safeText(pick(record, ["operational_classification"]), "ACTIVE"),
    operational_classification_reason: safeText(pick(record, ["operational_classification_reason", "archive_reason", "reason"])),
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
      missing_returnables: uniqueBy([...existing.missing_returnables, ...record.missing_returnables], (item) => item.toLowerCase()),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      proofs: uniqueBy([...existing.proofs, ...record.proofs], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      audit: [...existing.audit, ...record.audit].slice(0, 12),
      qualification_score: Math.max(existing.qualification_score, record.qualification_score),
      quote_readiness_score: Math.max(existing.quote_readiness_score, record.quote_readiness_score),
      submission_readiness_score: Math.max(existing.submission_readiness_score, record.submission_readiness_score),
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

function ScoreChip({ label, score }) {
  return (
    <span className={`rfq-score-chip ${scoreTone(score)}`}>
      <small>{label}</small>
      <b>{score}</b>
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

function SupplierValidationPanel({ rfq }) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!rfq?.reference) return;
      setState({ loading: true, data: null, error: "" });
      const result = await fetchEndpoint(`/rfq-lifecycle/supplier-validation/${encodeURIComponent(rfq.reference)}`);
      if (cancelled) return;
      if (result.ok) {
        setState({ loading: false, data: result.data, error: "" });
      } else {
        setState({ loading: false, data: null, error: result.error });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [rfq?.reference]);

  if (state.loading) return <div className="rfq-empty-inline">Loading supplier validation...</div>;
  if (state.error) return <div className="rfq-warning"><AlertTriangle size={16} />{state.error}</div>;

  const rows = asArray(state.data?.comparison_rows);
  const policy = state.data?.supplier_quote_requests_policy || {};
  return (
    <div className="rfq-pricing-workspace">
      <div className="rfq-pricing-summary">
        <span>Rows <b>{rows.length}</b></span>
        <span>Supplier quote lines <b>{state.data?.supplier_quote_line_count || 0}</b></span>
        <span>Target suppliers <b>{policy.target_supplier_quote_count || 3}</b></span>
        <span>Status <b>{state.data?.supplier_validation_required ? "Required" : "Validated"}</b></span>
      </div>
      <div className="rfq-safety-note">
        Internal validation only. Supplier outreach, Gmail drafts and external sending are disabled for this workspace.
      </div>
      <div className="rfq-pricing-table">
        {rows.map((row) => (
          <div className="rfq-pricing-row" key={row.row_id}>
            <div>
              <b>{row.item_number}</b>
              <span>{row.description}</span>
              <small>{row.quantity} {row.unit} · provisional {formatMoney(row.provisional_estimate?.unit_cost)}</small>
            </div>
            <label>
              Supplier quotes
              <strong>{row.supplier_quote_count || 0}</strong>
            </label>
            <label>
              Lowest compliant
              <strong>{row.lowest_compliant_cost ? formatMoney(row.lowest_compliant_cost) : "Pending"}</strong>
            </label>
            <label>
              Preferred
              <strong>{row.preferred_supplier?.supplier_name || "Operator selection required"}</strong>
            </label>
            <strong>{row.supplier_validation_status === "SUPPLIER_VALIDATED" ? "Validated" : "Review"}</strong>
            {asArray(row.supplier_quotes).length ? (
              <div className="rfq-detail-wide">
                {asArray(row.supplier_quotes).map((quote, index) => (
                  <p className={quote.eligible_for_preference ? "rfq-local-state" : "rfq-risk"} key={`${quote.supplier_name}-${index}`}>
                    {quote.supplier_name || "Supplier"} · {formatMoney(quote.unit_cost)} · {quote.stock_availability || "stock pending"} · {quote.lead_time || "lead time pending"}
                    {asArray(quote.missing_documents).length ? ` · blockers: ${asArray(quote.missing_documents).join(", ")}` : ""}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function ReturnablesReviewPanel({ rfq }) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState({ id: "", message: "", error: "" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!rfq?.reference) return;
      setState({ loading: true, data: null, error: "" });
      const result = await fetchEndpoint(`/rfq-lifecycle/returnables-review/${encodeURIComponent(rfq.reference)}`);
      if (cancelled) return;
      if (result.ok) {
        setState({ loading: false, data: result.data, error: "" });
      } else {
        setState({ loading: false, data: null, error: result.error });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [rfq?.reference]);

  if (state.loading) return <div className="rfq-empty-inline">Loading returnables review...</div>;
  if (state.error) return <div className="rfq-warning"><AlertTriangle size={16} />{state.error}</div>;

  const items = asArray(state.data?.returnables);
  const categories = state.data?.category_counts || {};
  const readiness = state.data?.readiness_counts || {};
  if (!items.length) {
    return <div className="rfq-empty-inline">No extracted returnables review model is available.</div>;
  }
  const grouped = items.reduce((acc, item) => {
    const category = item.category || "REQUIRES_MANUAL_CLASSIFICATION";
    if (!acc[category]) acc[category] = [];
    acc[category].push(item);
    return acc;
  }, {});

  function updateDraft(id, field, value) {
    setDrafts((current) => ({ ...current, [id]: { ...(current[id] || {}), [field]: value } }));
  }

  function primaryAction(item) {
    if (item.category === "REQUIRED_COMPANY_DOCUMENT" || item.category === "SUPPORTING_TECHNICAL_EVIDENCE") return "PRESENT";
    if (item.category === "BUYER_FORM_COMPLETION") return "COMPLETED";
    if (item.category === "PRICING_COMMERCIAL_RULE") return "CONFIRMED";
    if (item.category === "DEADLINE_SUBMISSION_RULE") return "CLOSING_DATE_VERIFIED";
    return "ACKNOWLEDGED";
  }

  function payloadFor(item, status) {
    const draft = drafts[item.returnable_id] || {};
    const payload = {
      review_status: status,
      approval_state: status === "REJECTED" || status === "NON_COMPLIANT" ? "REJECTED" : "REVIEWED",
      reviewer: draft.reviewer || "operator",
      review_note: draft.note || "",
      operator_override_justification: draft.overrideReason || "",
    };
    if (draft.evidenceRef) {
      payload.evidence_references = [{
        evidence_id: `${item.returnable_id}-evidence`,
        evidence_type: item.requires_buyer_form_workflow ? "buyer_form_reference" : "document_reference",
        document_reference: draft.evidenceRef,
        file_path: draft.evidenceRef,
        linked_by: payload.reviewer,
        description: draft.note || item.requirement_text,
      }];
      payload.evidence_file = draft.evidenceRef;
      payload.evidence_location = draft.evidenceRef;
      payload.buyer_form_reference = item.requires_buyer_form_workflow ? draft.evidenceRef : "";
    }
    return payload;
  }

  async function saveRequirement(item, status) {
    setSaving({ id: item.returnable_id, message: "", error: "" });
    const result = await patchEndpoint(
      `/rfq-lifecycle/returnables-review/${encodeURIComponent(rfq.reference)}/${encodeURIComponent(item.returnable_id)}`,
      payloadFor(item, status),
    );
    if (!result.ok || result.data?.status === "blocked") {
      setSaving({
        id: item.returnable_id,
        message: "",
        error: result.error || asArray(result.data?.errors).join(", ") || "Requirement update blocked.",
      });
      return;
    }
    setState({ loading: false, data: result.data, error: "" });
    setSaving({ id: item.returnable_id, message: "Review saved.", error: "" });
  }
  return (
    <div className="rfq-tab-panel">
      <div className="rfq-pricing-summary">
        <span>Returnables <b>{items.length}</b></span>
        <span>Documents missing <b>{readiness.documents_missing || state.data?.documents_missing || 0}</b></span>
        <span>Buyer forms <b>{readiness.buyer_forms_incomplete || state.data?.buyer_forms_incomplete || 0}</b></span>
        <span>Pricing rules <b>{readiness.pricing_rules_unconfirmed || state.data?.pricing_rules_unconfirmed || 0}</b></span>
        <span>Declarations <b>{categories.ELIGIBILITY_DECLARATION || 0}</b></span>
      </div>
      {Object.entries(grouped).map(([category, group]) => (
        <div className="rfq-checklist" key={category}>
          <h3 className="rfq-section-title">{category.replaceAll("_", " ")}</h3>
          {group.map((item) => (
            <div className={`rfq-check-row ${item.unresolved ? "missing" : "complete"}`} key={item.returnable_id}>
              {item.unresolved ? <ShieldAlert size={17} /> : <CheckCircle2 size={17} />}
              <div>
                <span>{item.requirement_text}</span>
                <small>
                  {item.review_status}
                  {item.source_page ? ` · p.${item.source_page}` : ""}
                  {item.requires_evidence ? " · evidence required" : item.requires_buyer_form_workflow ? " · buyer-form link required" : " · no upload required"}
                  {item.action_required ? ` · ${item.action_required}` : ""}
                </small>
                <div className="rfq-returnable-controls">
                  <input
                    type="text"
                    value={drafts[item.returnable_id]?.evidenceRef || ""}
                    onChange={(event) => updateDraft(item.returnable_id, "evidenceRef", event.target.value)}
                    placeholder={item.requires_buyer_form_workflow ? "Buyer form or BOQ reference" : item.requires_evidence ? "Existing evidence reference" : "Optional reference"}
                  />
                  <input
                    type="text"
                    value={drafts[item.returnable_id]?.note || ""}
                    onChange={(event) => updateDraft(item.returnable_id, "note", event.target.value)}
                    placeholder="Operator note"
                  />
                  <button type="button" onClick={() => saveRequirement(item, primaryAction(item))}>
                    {item.requires_evidence ? "Link Evidence" : item.requires_buyer_form_workflow ? "Link Buyer Form" : item.category === "PRICING_COMMERCIAL_RULE" ? "Confirm Compliant" : "Acknowledge"}
                  </button>
                  {item.category === "CONDITIONAL_REQUIREMENT" ? (
                    <button type="button" onClick={() => saveRequirement(item, "NOT_APPLICABLE")}>Not Applicable</button>
                  ) : null}
                  <button type="button" onClick={() => saveRequirement(item, "REQUIRES_CLARIFICATION")}>Requires Clarification</button>
                  <button type="button" onClick={() => saveRequirement(item, "REJECTED")}>Reject</button>
                  {saving.id === item.returnable_id && saving.message ? <small>{saving.message}</small> : null}
                  {saving.id === item.returnable_id && saving.error ? <small className="rfq-risk">{saving.error}</small> : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
      {state.data?.submission_blocked ? (
        <div className="rfq-warning"><AlertTriangle size={16} />Submission remains blocked until supplier validation, returnables review and human approval are complete.</div>
      ) : null}
    </div>
  );
}

function sourcePricingRows(rfq) {
  const raw = rfq?._raw || {};
  const candidates = [
    raw.pricing_rows,
    raw.pricing_schedule_rows,
    raw.buyer_pricing_schedule_rows,
    raw.line_items,
    raw.boq_items,
    raw.rfq_requirement_rows,
    raw.pricing_schedule?.rows,
  ];
  const rows = [];
  const seen = new Set();
  candidates.forEach((candidate) => {
    asArray(candidate).forEach((row, index) => {
      if (!row || typeof row !== "object") return;
      const key = safeText(pick(row, ["row_id", "item_number", "material_number", "buyer_line_number", "line_number"]), String(index + 1));
      if (seen.has(key)) return;
      seen.add(key);
      rows.push({
        row_id: key,
        item_number: safeText(pick(row, ["item_number", "material_number", "buyer_line_number", "line_number"]), key),
        description: safeText(pick(row, ["description", "item_description", "name"]), "Line item"),
        specification: safeText(pick(row, ["specification", "technical_specification"])),
        quantity: normalizeNumber(pick(row, ["quantity", "qty"]), 0),
        unit: safeText(pick(row, ["unit", "uom"]), "each"),
        unit_cost: pick(row, ["unit_cost", "cost_price", "supplier_rate", "supplier_unit_price"], ""),
        selling_price: pick(row, ["selling_price", "selling_rate", "unit_price"], ""),
        markup_percent: pick(row, ["markup_percent", "markup_pct", "markup"], 25),
        manual_override: Boolean(pick(row, ["manual_override", "selling_rate_manual_override"], false)),
        source_page: pick(row, ["source_page"], ""),
      });
    });
  });
  return rows;
}

function calculatePricingRows(rows, vatRate = 15) {
  return rows.map((row) => {
    const quantity = normalizeNumber(row.quantity, 0);
    const unitCost = normalizeNumber(row.unit_cost, 0);
    const markup = normalizeNumber(row.markup_percent, 25);
    const suppliedSelling = normalizeNumber(row.selling_price, 0);
    const selling = suppliedSelling > 0 ? suppliedSelling : unitCost > 0 ? Math.round(unitCost * (1 + markup / 100) * 100) / 100 : 0;
    const total = Math.round(quantity * selling * 100) / 100;
    const vat = Math.round(total * vatRate) / 100;
    return {
      ...row,
      quantity,
      unit_cost: unitCost || "",
      markup_percent: markup,
      selling_price: selling || "",
      total_ex_vat: total,
      vat_amount: vat,
      total_incl_vat: Math.round((total + vat) * 100) / 100,
      pricing_source: "operator_provisional_estimate",
      supplier_quote_received: false,
      requires_supplier_validation: true,
      pricing_status: "provisional",
      review_required: true,
    };
  });
}

function ManualPricingPanel({ rfq }) {
  const [rows, setRows] = useState(() => sourcePricingRows(rfq));
  const [status, setStatus] = useState({ loading: false, message: "", error: "" });
  const pricedRows = useMemo(() => calculatePricingRows(rows), [rows]);
  const subtotal = pricedRows.reduce((sum, row) => sum + normalizeNumber(row.total_ex_vat, 0), 0);
  const vat = pricedRows.reduce((sum, row) => sum + normalizeNumber(row.vat_amount, 0), 0);
  const cost = pricedRows.reduce((sum, row) => sum + normalizeNumber(row.quantity, 0) * normalizeNumber(row.unit_cost, 0), 0);
  const profit = subtotal - cost;

  useEffect(() => {
    let cancelled = false;
    async function loadManualPricing() {
      if (!rfq?.reference) return;
      setStatus({ loading: true, message: "", error: "" });
      const result = await fetchEndpoint(`/rfq-lifecycle/manual-pricing/${encodeURIComponent(rfq.reference)}`);
      if (cancelled) return;
      if (result.ok) {
        const incoming = asArray(result.data?.line_items || result.data?.pricing_rows);
        if (incoming.length) setRows(incoming);
        setStatus({
          loading: false,
          message: result.data?.saved ? "Saved provisional pricing loaded." : "Extracted rows loaded for provisional pricing.",
          error: "",
        });
      } else {
        setStatus({ loading: false, message: "", error: result.error });
      }
    }
    loadManualPricing();
    return () => {
      cancelled = true;
    };
  }, [rfq?.reference]);

  function updateRow(index, field, value) {
    setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value, manual_override: field === "selling_price" ? true : row.manual_override } : row));
  }

  async function savePricing() {
    setStatus({ loading: true, message: "", error: "" });
    const result = await postEndpoint(`/rfq-lifecycle/manual-pricing/${encodeURIComponent(rfq.reference)}`, {
      line_items: pricedRows,
      pricing_source: "operator_provisional_estimate",
      supplier_quote_received: false,
      requires_supplier_validation: true,
      pricing_status: "provisional",
      operator_note: "Phase 34.1 controlled provisional pricing validation",
      vat_rate: 15,
    });
    if (!result.ok) {
      setStatus({ loading: false, message: "", error: result.error });
      return;
    }
    setRows(asArray(result.data?.line_items || pricedRows));
    setStatus({ loading: false, message: "Provisional pricing saved for operator review.", error: "" });
  }

  if (!pricedRows.length) {
    return <div className="rfq-empty-inline">No extracted pricing rows available for manual pricing.</div>;
  }

  return (
    <div className="rfq-pricing-workspace">
      <div className="rfq-pricing-summary">
        <span>Rows <b>{pricedRows.length}</b></span>
        <span>Subtotal <b>{formatMoney(subtotal)}</b></span>
        <span>VAT <b>{formatMoney(vat)}</b></span>
        <span>Profit <b>{formatMoney(profit)}</b></span>
      </div>
      <div className="rfq-pricing-table">
        {pricedRows.map((row, index) => (
          <div className="rfq-pricing-row" key={`${row.row_id || row.item_number}-${index}`}>
            <div>
              <b>{row.item_number}</b>
              <span>{row.description}</span>
              <small>{row.quantity} {row.unit}{row.source_page ? ` · p.${row.source_page}` : ""}</small>
            </div>
            <label>
              Cost
              <input type="number" min="0" step="0.01" value={row.unit_cost} onChange={(event) => updateRow(index, "unit_cost", event.target.value)} />
            </label>
            <label>
              Markup
              <input type="number" min="0" step="0.01" value={row.markup_percent} onChange={(event) => updateRow(index, "markup_percent", event.target.value)} />
            </label>
            <label>
              Selling
              <input type="number" min="0" step="0.01" value={row.selling_price} onChange={(event) => updateRow(index, "selling_price", event.target.value)} />
            </label>
            <strong>{formatMoney(row.total_ex_vat)}</strong>
          </div>
        ))}
      </div>
      <div className="rfq-pricing-footer">
        <span>Provisional estimate · supplier validation required · manual approval required</span>
        <button type="button" onClick={savePricing} disabled={status.loading}>{status.loading ? "Saving..." : "Save Provisional Pricing"}</button>
      </div>
      {status.message ? <div className="rfq-local-state">{status.message}</div> : null}
      {status.error ? <div className="rfq-warning"><AlertTriangle size={16} />{status.error}</div> : null}
    </div>
  );
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

    if (!response.ok) {
      throw new Error(
        data?.detail ||
        data?.message ||
        `${response.status} ${response.statusText}`
      );
    }

    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "Request failed",
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function patchEndpoint(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
      signal: controller.signal,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data?.detail ||
        data?.message ||
        `${response.status} ${response.statusText}`
      );
    }

    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      error: error?.message || "Request failed",
    };
  } finally {
    clearTimeout(timeout);
  }
}

function DetailDrawer({ rfq, activeTab, setActiveTab, onClose, operatorState, onOperatorAction, onGenerateQuotePack, quotePackGeneration }) {
  if (!rfq) return null;
  const urgency = urgencyMeta(rfq.closing_date);
  const localDecision = operatorState[rfq.id];
  const readOnlyRecord = rfq.operational_classification !== "ACTIVE";

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

        {readOnlyRecord ? (
          <div className="rfq-warning">
            <History size={16} />
            {rfq.operational_classification === "HISTORICAL"
              ? "Historical RFQ records are read-only and excluded from active pricing, quote and submission queues."
              : "This RFQ requires classification review before it can enter active operations."}
          </div>
        ) : (
          <div className="rfq-operator-actions">
            <button type="button" onClick={() => onOperatorAction(rfq.id, "Marked for Review")}><AlertTriangle size={15} />Mark for Review</button>
            <button type="button" onClick={() => onOperatorAction(rfq.id, "On Hold")}><PauseCircle size={15} />Hold</button>
            <button type="button" onClick={() => onOperatorAction(rfq.id, "Approved for Quote Prep")}><ThumbsUp size={15} />Approve for Quote Prep</button>
            <button
              type="button"
              disabled={quotePackGeneration?.loading}
              onClick={() => onGenerateQuotePack(rfq)}
            >
              <FolderOpen size={15} />
              {quotePackGeneration?.loading ? "Generating Quote Pack…" : "Generate Quote Pack"}
            </button>
            <button type="button" onClick={() => onOperatorAction(rfq.id, "Rejected Opportunity")}><Ban size={15} />Reject Opportunity</button>
          </div>
        )}
        {localDecision ? <div className="rfq-local-state">Local operator state: {localDecision}</div> : null}
        {quotePackGeneration?.error ? (
          <div className="rfq-warning">
            <AlertTriangle size={16} />
            {quotePackGeneration.error}
          </div>
        ) : null}
        {quotePackGeneration?.message ? (
          <div className="rfq-local-state">{quotePackGeneration.message}</div>
        ) : null}

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
              <div className="rfq-detail-wide">
                <h3>Recommended Action</h3>
                <p>{rfq.recommended_action}</p>
              </div>
              <div className="rfq-detail-wide">
                <h3>Risks</h3>
                {rfq.risks.length ? rfq.risks.map((risk) => <p className="rfq-risk" key={risk}>{risk}</p>) : <p>No major risks detected.</p>}
              </div>
            </div>
          ) : null}

          {activeTab === "Documents" ? <ArtifactList items={rfq.documents} empty="No buyer forms or source documents detected." /> : null}
          {activeTab === "BOQ / Pricing" ? (
            <>
              <h3 className="rfq-section-title">BOQs</h3>
              <ArtifactList items={rfq.boqs} empty="No BOQ detected." />
              <h3 className="rfq-section-title">Pricing Schedules</h3>
              <ArtifactList items={rfq.pricing_schedules} empty="No pricing schedule detected." />
              <h3 className="rfq-section-title">Manual Pricing</h3>
              <ManualPricingPanel rfq={rfq} />
            </>
          ) : null}
          {activeTab === "Supplier Validation" ? <SupplierValidationPanel rfq={rfq} /> : null}
          {activeTab === "Qualification" ? (
            <div className="rfq-tab-panel">
              <ScoreChip label="Qualification" score={rfq.qualification_score} />
              <ReturnablesReviewPanel rfq={rfq} />
            </div>
          ) : null}
          {activeTab === "Submission Readiness" ? (
            <div className="rfq-tab-panel">
              <ScoreChip label="Submission" score={rfq.submission_readiness_score} />
              <ReturnablesReviewPanel rfq={rfq} />
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
  const [historicalRfqs, setHistoricalRfqs] = useState([]);
  const [reviewRfqs, setReviewRfqs] = useState([]);
  const [workspaceMode, setWorkspaceMode] = useState("ACTIVE");
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [status, setStatus] = useState("All");
  const [readiness, setReadiness] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});
  const [quotePackGeneration, setQuotePackGeneration] = useState({
    loading: false,
    rfqId: "",
    packId: "",
    message: "",
    error: "",
  });

  useEffect(() => {
    let cancelled = false;
    async function loadRfqs() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(RFQ_ENDPOINTS.map((path) => fetchEndpoint(path)));
      const archiveResults = await Promise.all(HISTORICAL_ENDPOINTS.map((path) => fetchEndpoint(path)));
      const reviewResults = await Promise.all(CLASSIFICATION_REVIEW_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeRfqRecord({ ...record, operational_classification: "ACTIVE" }, record._sourcePath));
      const archivedRecords = archiveResults
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeRfqRecord({ ...record, operational_classification: "HISTORICAL" }, record._sourcePath));
      const reviewRecords = reviewResults
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeRfqRecord({ ...record, operational_classification: "REVIEW_REQUIRED" }, record._sourcePath));

      const merged = mergeRfqs(records).filter((rfq) => rfq.reference !== "RFQ" || rfq.title !== "RFQ");
      setRfqs(merged.length ? merged : []);
      setHistoricalRfqs(mergeRfqs(archivedRecords));
      setReviewRfqs(mergeRfqs(reviewRecords));
      setEndpointState({
        loading: false,
        results: [...results, ...archiveResults, ...reviewResults],
        error: results.some((result) => result.ok) ? "" : "No RFQ endpoints responded with usable data.",
      });
    }

    loadRfqs();
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleSource = workspaceMode === "HISTORICAL" ? historicalRfqs : workspaceMode === "REVIEW_REQUIRED" ? reviewRfqs : rfqs;
  const statuses = useMemo(() => ["All", ...uniqueBy(visibleSource.map((rfq) => rfq.status), (item) => item).filter(Boolean)], [visibleSource]);
  const selectedRfq = useMemo(() => visibleSource.find((rfq) => rfq.id === selectedId), [selectedId, visibleSource]);

  const filteredRfqs = useMemo(() => {
    const term = query.trim().toLowerCase();
    return visibleSource.filter((rfq) => {
      const haystack = `${rfq.reference} ${rfq.title} ${rfq.buyer} ${rfq.source}`.toLowerCase();
      const readinessMatch =
        readiness === "All" ||
        (readiness === "Quote Ready" && rfq.quote_readiness_score >= 80) ||
        (readiness === "Submission Ready" && rfq.submission_readiness_score >= 80) ||
        (readiness === "Needs Review" && (rfq.submission_readiness_score < 80 || rfq.missing_returnables.length > 0)) ||
        (readiness === "High Risk" && (rfq.qualification_score < 50 || rfq.submission_readiness_score < 50)) ||
        (readiness === "Closing Soon" && daysUntil(rfq.closing_date) <= 7);
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || rfq.province === province) &&
        (status === "All" || rfq.status === status) &&
        readinessMatch
      );
    });
  }, [province, query, readiness, status, visibleSource]);

  const summary = useMemo(() => ({
    total: rfqs.length,
    quoteReady: rfqs.filter((rfq) => rfq.quote_readiness_score >= 80).length,
    submissionReady: rfqs.filter((rfq) => rfq.submission_readiness_score >= 80).length,
    review: rfqs.filter((rfq) => rfq.missing_returnables.length || rfq.risks.length).length,
    archived: historicalRfqs.length,
    classificationReview: reviewRfqs.length,
  }), [historicalRfqs.length, reviewRfqs.length, rfqs]);

  function openRfq(rfq) {
    setSelectedId(rfq.id);
    setActiveTab("Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  async function generateQuotePackFromRfq(rfq) {
    if (!rfq || rfq._demo) {
      setQuotePackGeneration({
        loading: false,
        rfqId: rfq?.id || "",
        packId: "",
        message: "",
        error: "Quote-pack generation requires a live RFQ record.",
      });
      return;
    }

    setQuotePackGeneration({
      loading: true,
      rfqId: rfq.id,
      packId: "",
      message: "",
      error: "",
    });

    const response = await postEndpoint(
      "/quote-compilation/generate-local-pack",
      {
        id: rfq.id,
        rfq_id: rfq.id,
        rfq_reference: rfq.reference,
        reference: rfq.reference,
        title: rfq.title,
        buyer: rfq.buyer,
      }
    );

    if (!response.ok) {
      setQuotePackGeneration({
        loading: false,
        rfqId: rfq.id,
        packId: "",
        message: "",
        error: response.error || "Quote-pack generation failed.",
      });
      return;
    }

    const packId =
      response.data?.manifest?.pack_id ||
      response.data?.pack_id ||
      "";

    setOperatorState((prev) => ({
      ...prev,
      [rfq.id]: "Local Quote Pack Generated",
    }));

    setQuotePackGeneration({
      loading: false,
      rfqId: rfq.id,
      packId,
      message: packId
        ? `Quote pack ${packId} generated. Opening Quote Pack Engine.`
        : "Quote pack generated. Opening Quote Pack Engine.",
      error: "",
    });

    window.dispatchEvent(
      new CustomEvent("lmcp-open-quote-pack", {
        detail: {
          packId,
          rfqId: rfq.id,
          rfqReference: rfq.reference,
        },
      })
    );
  }

  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = false;

  return (
    <section className="rfq-ops-workspace" id="rfq-operations">
      <div className="rfq-ops-hero card">
        <div>
          <p className="eyebrow">RFQ Operations</p>
          <h1>RFQ Operations Workspace</h1>
          <p className="muted">Read-only workspace probing {API_BASE}. Operator decisions stay local unless a safe review endpoint is added later.</p>
        </div>
        <div className="rfq-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${RFQ_ENDPOINTS.length + HISTORICAL_ENDPOINTS.length + CLASSIFICATION_REVIEW_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="rfq-summary-grid">
        <div className="rfq-summary-card"><span>Active RFQs</span><b>{summary.total}</b></div>
        <div className="rfq-summary-card good"><span>Quote Ready</span><b>{summary.quoteReady}</b></div>
        <div className="rfq-summary-card blue"><span>Submission Ready</span><b>{summary.submissionReady}</b></div>
        <div className="rfq-summary-card amber"><span>Operational Review</span><b>{summary.review}</b></div>
        <div className="rfq-summary-card"><span>Historical Archive</span><b>{summary.archived}</b></div>
        <div className="rfq-summary-card amber"><span>Classification Review</span><b>{summary.classificationReview}</b></div>
      </div>

      <div className="rfq-toolbar card">
        {[
          ["ACTIVE", "Active RFQs"],
          ["HISTORICAL", "Historical RFQs"],
          ["REVIEW_REQUIRED", "Classification Review"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={workspaceMode === key ? "rfq-row-button active" : "rfq-row-button"}
            onClick={() => {
              setWorkspaceMode(key);
              setSelectedId("");
            }}
          >
            {label}
          </button>
        ))}
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
      {workspaceMode === "ACTIVE" && !endpointState.loading && !rfqs.length ? (
        <div className="rfq-warning">
          <FolderOpen size={16} />
          No active RFQs are currently available. Historical RFQs have been moved to the archive. Run a controlled manual harvest to discover current opportunities.
        </div>
      ) : null}

      <div className="rfq-table-card card">
        <div className="card-head">
          <h2>{workspaceMode === "HISTORICAL" ? "Historical RFQ Archive" : workspaceMode === "REVIEW_REQUIRED" ? "Classification Review Queue" : "Active RFQ Queue"}</h2>
          <span>{filteredRfqs.length} visible</span>
        </div>
        <div className="rfq-table-scroll">
          <table className="rfq-table">
            <thead>
              <tr>
                <th>RFQ</th>
                <th>Buyer</th>
                <th>Province</th>
                <th>Status</th>
                <th>Scores</th>
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
                    <td><span className="pill">{operatorState[rfq.id] || rfq.status}</span></td>
                    <td>
                      <div className="rfq-row-scores">
                        <ScoreChip label="Q" score={rfq.qualification_score} />
                        <ScoreChip label="P" score={rfq.quote_readiness_score} />
                        <ScoreChip label="S" score={rfq.submission_readiness_score} />
                      </div>
                    </td>
                    <td><span className={`rfq-urgency ${urgency.tone}`}><Clock3 size={14} />{urgency.label}</span></td>
                    <td>{rfq.missing_returnables.length}</td>
                    <td><button type="button" className="rfq-row-button" onClick={(event) => { event.stopPropagation(); openRfq(rfq); }}>Open</button></td>
                  </tr>
                );
              })}
              {!filteredRfqs.length ? (
                <tr>
                  <td colSpan="8">
                    <div className="rfq-empty-inline">
                      {workspaceMode === "ACTIVE"
                        ? "No active RFQs are currently available."
                        : "No RFQs match the current filters."}
                    </div>
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
        onGenerateQuotePack={generateQuotePackFromRfq}
        quotePackGeneration={
          quotePackGeneration.rfqId === selectedRfq?.id
            ? quotePackGeneration
            : null
        }
      />
    </section>
  );
}
