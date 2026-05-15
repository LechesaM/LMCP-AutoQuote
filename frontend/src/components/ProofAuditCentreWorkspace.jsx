import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileArchive,
  FileCheck2,
  FileText,
  Filter,
  Flag,
  History,
  Image,
  PauseCircle,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { API_BASE } from "../services/api";

const REQUEST_TIMEOUT_MS = 8000;

const PROOF_ENDPOINTS = [
  "/submission-history/recent",
  "/submission-history/recent-with-proofs",
  "/submission-history/proof-sync",
  "/submission-proof/latest",
  "/submission-proof/status",
  "/proof-center",
  "/proof-center/scan",
  "/proof-center/health",
  "/health",
];

const PROVINCES = ["All", "GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP", "Unknown"];
const DRAWER_TABS = ["Overview", "Proof Files", "Screenshots", "Timeline", "Verification", "Audit", "Risks"];
const TIMELINE_STATES = ["generated", "uploaded", "verified", "blocked", "review_required"];

const DEMO_PROOFS = [
  {
    id: "demo-proof-audit",
    rfq_reference: "RFQ-PROOF-DEMO-001",
    title: "Controlled submission proof preview",
    buyer: "Demo Buyer",
    province: "GP",
    submission_status: "Dry-Run Review",
    proof_status: "Generated",
    proof_generated_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    screenshots: [{ name: "Portal review screenshot", type: "Screenshot", status: "Ready" }],
    proof_files: [{ name: "submission_receipt.json", type: "Proof File", status: "Ready" }],
    portal: "Demo portal",
    verification_status: "Review Required",
    verification_required: true,
    audit_flags: ["Demo fallback data"],
    blockers: [],
    timeline: [
      { state: "generated", label: "Proof generated", timestamp: new Date(Date.now() - 2 * 3600000).toISOString(), message: "Proof artifact captured" },
      { state: "review_required", label: "Verification review", timestamp: new Date(Date.now() - 90 * 60000).toISOString(), message: "Manual verification still required" },
    ],
    operator_notes: ["Fallback row shown because live proof records did not load"],
    risks: ["Proof verification has not been completed"],
    recommended_next_step: "Escalate review",
    _demo: true,
    _sources: ["frontend fallback"],
  },
];

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

function normalizeSubmissionStatus(value, record = {}) {
  const raw = safeText(value || record.submission_status || record.status || record.pipeline_status || record.lifecycle_state, "Unknown");
  const lower = raw.toLowerCase();
  if (lower.includes("submit") || lower.includes("proof")) return "Submitted";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("reject")) return "Blocked";
  if (lower.includes("review")) return "Review Required";
  if (lower.includes("dry")) return "Dry-Run Review";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeProofStatus(value, present = false) {
  const raw = safeText(value, present ? "Generated" : "Missing");
  const lower = raw.toLowerCase();
  if (lower.includes("verified")) return "Verified";
  if (lower.includes("generated") || lower.includes("captured") || lower.includes("ready") || lower.includes("ok")) return "Generated";
  if (lower.includes("review") || lower.includes("pending")) return "Review Required";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("missing")) return "Blocked";
  return raw.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeVerificationStatus(value, required, proofStatus) {
  const raw = safeText(value);
  const lower = raw.toLowerCase();
  if (lower.includes("verified") || proofStatus === "Verified") return "Verified";
  if (lower.includes("block") || lower.includes("fail")) return "Blocked";
  if (lower.includes("review") || required) return "Review Required";
  if (lower.includes("pending")) return "Pending";
  return proofStatus === "Generated" ? "Pending" : "Review Required";
}

function statusTone(status) {
  const lower = safeText(status).toLowerCase();
  if (lower.includes("verified") || lower.includes("generated") || lower.includes("healthy") || lower.includes("submitted")) return "green";
  if (lower.includes("review") || lower.includes("pending") || lower.includes("dry")) return "amber";
  if (lower.includes("block") || lower.includes("fail") || lower.includes("missing") || lower.includes("risk")) return "red";
  return "neutral";
}

function normalizeArtifact(value, type = "Proof File") {
  if (!value) return null;
  if (typeof value === "string") {
    return { name: value.split("/").pop() || value, url: value.startsWith("http") || value.startsWith("/") ? value : "", type, status: "Ready" };
  }
  if (typeof value !== "object") return null;
  const url = safeText(pick(value, ["url", "href", "path", "file_path", "local_path", "download_url", "source_url", "screenshot_url", "image_url"]));
  const name =
    safeText(pick(value, ["name", "filename", "file_name", "title", "label", "document_name", "record_id"])) ||
    (url ? url.split("/").pop() : type);
  return {
    name,
    url,
    type: safeText(pick(value, ["type", "document_type", "category"]), type),
    status: normalizeProofStatus(pick(value, ["status", "state", "proof_status"]), true),
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
      .filter((doc) => pattern.test(`${doc.name} ${doc.type} ${doc.url}`))
      .map((doc) => ({ ...doc, type })),
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
}

function namedList(values) {
  return values
    .map((item) => safeText(typeof item === "object" ? pick(item, ["name", "label", "field", "document", "reason", "message", "type"]) : item))
    .filter(Boolean);
}

function isProofLike(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const keys = Object.keys(record).join(" ").toLowerCase();
  return /(proof|receipt|screenshot|submission|audit|verification|verified|portal|rfq|buyer|timeline|blocker|risk|trace)/.test(keys);
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

    if (isProofLike(value)) {
      const sig = `${sourcePath}:${safeText(pick(value, ["id", "record_id", "proof_id", "rfq_id", "reference", "rfq_number", "buyer_rfq_number", "title", "description"]), JSON.stringify(Object.keys(value).slice(0, 12)))}`;
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

function normalizeTimelineEvent(value, fallbackState = "generated") {
  if (typeof value === "string") {
    const lower = value.toLowerCase();
    const state = TIMELINE_STATES.find((item) => lower.includes(item.replace("_", " "))) || fallbackState;
    return { state, label: value, timestamp: "", message: value };
  }
  if (!value || typeof value !== "object") return null;
  const rawState = safeText(pick(value, ["state", "status", "event", "type", "action"]), fallbackState).toLowerCase();
  const state =
    TIMELINE_STATES.find((item) => rawState.includes(item) || rawState.includes(item.replace("_", " "))) ||
    (rawState.includes("upload") || rawState.includes("submit") ? "uploaded" : fallbackState);
  return {
    state,
    label: safeText(pick(value, ["label", "title", "event", "action", "status"]), state.replaceAll("_", " ")),
    timestamp: safeText(pick(value, ["timestamp", "created_at", "submitted_at", "proof_generated_at", "time", "date"])),
    message: safeText(pick(value, ["message", "reason", "description", "detail"]), ""),
  };
}

function deriveTimeline(record, proofGeneratedAt, proofStatus, verificationStatus, blockers) {
  const explicit = asArray(pick(record, ["timeline", "events", "history", "audit_timeline"]))
    .map((item) => normalizeTimelineEvent(item))
    .filter(Boolean);
  const inferred = [];
  if (proofGeneratedAt) inferred.push({ state: "generated", label: "Proof generated", timestamp: proofGeneratedAt, message: "Proof artifact detected" });
  if (/submitted|uploaded/i.test(safeText(record.submission_status || record.status))) inferred.push({ state: "uploaded", label: "Submission uploaded", timestamp: safeText(pick(record, ["submitted_at", "uploaded_at", "finished_at"])), message: "Submission status indicates upload/submission" });
  if (verificationStatus === "Verified") inferred.push({ state: "verified", label: "Proof verified", timestamp: safeText(pick(record, ["verified_at", "updated_at"])), message: "Verification completed" });
  if (blockers.length) inferred.push({ state: "blocked", label: "Blocked", timestamp: "", message: blockers[0] });
  if (verificationStatus === "Review Required" || proofStatus === "Review Required") inferred.push({ state: "review_required", label: "Review required", timestamp: "", message: "Manual proof review required" });
  return uniqueBy([...explicit, ...inferred], (item) => `${item.state}:${item.timestamp}:${item.label}:${item.message}`.toLowerCase()).slice(0, 12);
}

function latestTimestamp(record) {
  const values = [
    record.proof_generated_at,
    ...record.timeline.map((item) => item.timestamp),
  ].filter(Boolean);
  const times = values.map((item) => new Date(item).getTime()).filter(Number.isFinite);
  return times.length ? Math.max(...times) : 0;
}

function normalizeProofRecord(record, sourcePath) {
  const rfqReference = safeText(
    pick(record, ["rfq_reference", "reference", "rfq_number", "buyer_rfq_number", "bid_number", "tender_number", "id", "rfq_id", "record_id"]),
    "RFQ",
  );
  const title = safeText(pick(record, ["title", "description", "name", "opportunity_title", "tender_title", "subject"]), rfqReference);
  const buyer = safeText(pick(record, ["buyer", "buyer_name", "department", "organisation", "organization", "client", "entity"]), "Unknown Buyer");
  const province = normalizeProvince(pick(record, ["province", "buyer_province", "region", "location"]));
  const baseFiles = uniqueBy(
    [
      ...collectArtifacts(record, ["proof_files", "files", "proofs", "receipts", "documents", "submission_proofs", "proof_records"], "Proof File"),
      ...collectArtifacts(record, ["receipt", "proof_file", "proof_json", "proof_pdf"], "Proof File"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const screenshots = uniqueBy(
    [
      ...collectArtifacts(record, ["screenshots", "screenshot_files", "proof_screenshots", "images", "portal_screenshots"], "Screenshot"),
      ...inferArtifacts(baseFiles, /\.(png|jpg|jpeg|webp)$/i, "Screenshot"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const proofFiles = uniqueBy(
    [
      ...baseFiles,
      ...inferArtifacts(baseFiles, /\.(json|pdf|txt|html)$/i, "Proof File"),
    ],
    (item) => `${item.type}:${item.url || item.name}`.toLowerCase(),
  );
  const proofGeneratedAt = safeText(pick(record, ["proof_generated_at", "created_at", "submitted_at", "finished_at", "timestamp"]));
  const submissionStatus = normalizeSubmissionStatus(pick(record, ["submission_status", "status", "pipeline_status", "stage"]), record);
  const proofStatus = normalizeProofStatus(pick(record, ["proof_status", "status", "verification_status"]), proofFiles.length || screenshots.length);
  const verificationRequiredRaw = pick(record, ["verification_required", "requires_verification", "review_required"]);
  const verificationRequired = verificationRequiredRaw === undefined ? proofStatus !== "Verified" : Boolean(verificationRequiredRaw);
  const verificationStatus = normalizeVerificationStatus(pick(record, ["verification_status", "verified_status", "review_status"]), verificationRequired, proofStatus);
  const auditFlags = uniqueBy(namedList(asArray(pick(record, ["audit_flags", "flags", "audit_warnings", "warnings", "alerts"]))), (item) => item.toLowerCase());
  const blockers = uniqueBy(namedList(asArray(pick(record, ["blockers", "blocking_reasons", "production_lock_reasons", "hard_blockers"]))), (item) => item.toLowerCase());
  const risks = uniqueBy(
    [
      ...namedList(asArray(pick(record, ["risks", "risk_flags", "risk_notes"]))),
      verificationRequired && "Verification required",
      blockers.length && `${blockers.length} blocker(s) present`,
      auditFlags.length && `${auditFlags.length} audit flag(s) present`,
    ].filter(Boolean),
    (item) => item.toLowerCase(),
  ).slice(0, 8);
  const timeline = deriveTimeline(record, proofGeneratedAt, proofStatus, verificationStatus, blockers);
  const operatorNotes = uniqueBy(namedList(asArray(pick(record, ["operator_notes", "notes", "comments", "review_notes"]))), (item) => item.toLowerCase());
  const portal = safeText(pick(record, ["portal", "source", "portal_name", "submission_portal", "origin"]), sourcePath);
  const id = slug(pick(record, ["id", "record_id", "proof_id", "submission_id", "rfq_id"], "") || `${rfqReference}-${title}`) || `proof-${Math.random().toString(36).slice(2)}`;
  const recommendedNextStep =
    safeText(pick(record, ["recommended_next_step", "recommended_action", "next_action", "operator_action"])) ||
    (blockers.length ? "Hold proof" : verificationRequired ? "Escalate review" : "Mark verified");

  return {
    id,
    rfq_reference: rfqReference,
    title,
    buyer,
    province,
    submission_status: submissionStatus,
    proof_status: proofStatus,
    proof_generated_at: proofGeneratedAt,
    screenshots,
    proof_files: proofFiles,
    portal,
    verification_status: verificationStatus,
    verification_required: verificationRequired,
    audit_flags: auditFlags,
    blockers,
    timeline,
    operator_notes: operatorNotes,
    risks,
    recommended_next_step: recommendedNextStep,
    _sources: [sourcePath],
    _raw: record,
  };
}

function mergeProofs(records) {
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
      ...Object.fromEntries(Object.entries(record).filter(([, value]) => value !== "" && value !== undefined && value !== null)),
      id: existing.id,
      rfq_reference: existing.rfq_reference !== "RFQ" ? existing.rfq_reference : record.rfq_reference,
      title: existing.title !== existing.rfq_reference ? existing.title : record.title,
      buyer: existing.buyer !== "Unknown Buyer" ? existing.buyer : record.buyer,
      province: existing.province !== "Unknown" ? existing.province : record.province,
      screenshots: uniqueBy([...existing.screenshots, ...record.screenshots], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      proof_files: uniqueBy([...existing.proof_files, ...record.proof_files], (item) => `${item.type}:${item.url || item.name}`.toLowerCase()),
      audit_flags: uniqueBy([...existing.audit_flags, ...record.audit_flags], (item) => item.toLowerCase()),
      blockers: uniqueBy([...existing.blockers, ...record.blockers], (item) => item.toLowerCase()),
      timeline: uniqueBy([...existing.timeline, ...record.timeline], (item) => `${item.state}:${item.timestamp}:${item.label}`.toLowerCase()).slice(0, 12),
      operator_notes: uniqueBy([...existing.operator_notes, ...record.operator_notes], (item) => item.toLowerCase()),
      risks: uniqueBy([...existing.risks, ...record.risks], (item) => item.toLowerCase()).slice(0, 8),
      _sources: uniqueBy([...existing._sources, ...record._sources], (item) => item),
      _raw: existing._raw,
    });
  }
  return [...map.values()].sort((a, b) => latestTimestamp(b) - latestTimestamp(a));
}

function recentMatch(record, filter) {
  if (filter === "All") return true;
  const latest = latestTimestamp(record);
  if (!latest) return false;
  const ageMs = Date.now() - latest;
  if (filter === "24h") return ageMs <= 24 * 3600000;
  if (filter === "7d") return ageMs <= 7 * 86400000;
  if (filter === "30d") return ageMs <= 30 * 86400000;
  return true;
}

function formatDateTime(value) {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return safeText(value, "No timestamp");
  return date.toLocaleString("en-ZA", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
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

function StatusChip({ label, status }) {
  return (
    <span className={`proof-status-chip ${statusTone(status)}`}>
      <small>{label}</small>
      <b>{status}</b>
    </span>
  );
}

function TimelineChip({ state }) {
  return <span className={`proof-timeline-chip ${state}`}>{state.replaceAll("_", " ")}</span>;
}

function ProofFileList({ items, empty }) {
  if (!items.length) return <div className="proof-audit-empty-inline">{empty}</div>;
  return (
    <div className="proof-audit-file-list">
      {items.map((item, index) => (
        <div className="proof-audit-file" key={`${item.type}-${item.name}-${index}`}>
          {item.type === "Screenshot" ? <Image size={16} /> : item.type === "Proof File" ? <FileArchive size={16} /> : <FileText size={16} />}
          <div>
            <b>{item.name}</b>
            <span>{item.type}{item.status ? ` - ${item.status}` : ""}</span>
          </div>
          {item.url ? <a href={item.url.startsWith("http") ? item.url : `${API_BASE}${item.url}`} target="_blank" rel="noreferrer">Open</a> : null}
        </div>
      ))}
    </div>
  );
}

function ScreenshotPanel({ screenshots }) {
  if (!screenshots.length) return <div className="proof-audit-empty-inline">No screenshots detected for the focused proof.</div>;
  return (
    <div className="proof-screenshot-grid">
      {screenshots.map((shot, index) => (
        <div className="proof-screenshot-card" key={`${shot.name}-${index}`}>
          {shot.url ? <img src={shot.url.startsWith("http") ? shot.url : `${API_BASE}${shot.url}`} alt={shot.name} /> : <div><Image size={24} /><span>No preview URL</span></div>}
          <b>{shot.name}</b>
          <small>{shot.status}</small>
        </div>
      ))}
    </div>
  );
}

function TimelineFeed({ records, onOpen }) {
  const events = records
    .flatMap((record) => record.timeline.map((event, index) => ({ ...event, record, key: `${record.id}-${event.state}-${event.timestamp}-${index}` })))
    .sort((a, b) => (new Date(b.timestamp || 0).getTime() || 0) - (new Date(a.timestamp || 0).getTime() || 0))
    .slice(0, 30);
  if (!events.length) return <div className="proof-audit-empty-inline">No proof timeline events available yet.</div>;
  return (
    <div className="proof-timeline-feed">
      {events.map((event) => (
        <button type="button" key={event.key} onClick={() => onOpen(event.record)}>
          <TimelineChip state={event.state} />
          <div>
            <b>{event.label}</b>
            <span>{event.record.rfq_reference} - {event.record.buyer}</span>
            <small>{formatDateTime(event.timestamp)}{event.message ? ` - ${event.message}` : ""}</small>
          </div>
        </button>
      ))}
    </div>
  );
}

function DetailDrawer({ proof, activeTab, setActiveTab, onClose, operatorState, onOperatorAction }) {
  if (!proof) return null;
  const localDecision = operatorState[proof.id];

  return (
    <div className="proof-audit-drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="proof-audit-drawer" aria-label="Proof and audit detail" onMouseDown={(event) => event.stopPropagation()}>
        <div className="proof-audit-drawer-head">
          <div>
            <span className="proof-audit-kicker">{proof.rfq_reference}</span>
            <h2>{proof.title}</h2>
            <p>{proof.buyer} - {proof.portal} - {formatDateTime(proof.proof_generated_at)}</p>
          </div>
          <button className="proof-audit-icon-button" type="button" onClick={onClose} aria-label="Close proof detail">
            <X size={18} />
          </button>
        </div>

        <div className="proof-audit-scorebar">
          <StatusChip label="Proof" status={proof.proof_status} />
          <StatusChip label="Verification" status={proof.verification_status} />
          <StatusChip label="Submission" status={proof.submission_status} />
        </div>

        <div className="proof-audit-actions">
          <button type="button" onClick={() => onOperatorAction(proof.id, "Marked Verified")}><CheckCircle2 size={15} />Mark Verified</button>
          <button type="button" onClick={() => onOperatorAction(proof.id, "Escalated Review")}><ShieldAlert size={15} />Escalate Review</button>
          <button type="button" onClick={() => onOperatorAction(proof.id, "Proof Held")}><PauseCircle size={15} />Hold Proof</button>
          <button type="button" onClick={() => onOperatorAction(proof.id, "Audit Risk Flagged")}><Flag size={15} />Flag Audit Risk</button>
        </div>
        {localDecision ? <div className="proof-audit-local-state">Local operator state: {localDecision}</div> : null}

        <div className="proof-audit-tabs" role="tablist">
          {DRAWER_TABS.map((tab) => (
            <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="proof-audit-drawer-body">
          {activeTab === "Overview" ? (
            <div className="proof-audit-detail-grid">
              <div className="proof-audit-detail-card"><span>Proof</span><b>{proof.proof_status}</b></div>
              <div className="proof-audit-detail-card"><span>Verification</span><b>{proof.verification_status}</b></div>
              <div className="proof-audit-detail-card"><span>Portal</span><b>{proof.portal}</b></div>
              <div className="proof-audit-detail-card"><span>Review Required</span><b>{proof.verification_required ? "Yes" : "No"}</b></div>
              <div className="proof-audit-detail-wide"><h3>Recommended Next Step</h3><p>{proof.recommended_next_step}</p></div>
            </div>
          ) : null}
          {activeTab === "Proof Files" ? <ProofFileList items={proof.proof_files} empty="No proof files detected." /> : null}
          {activeTab === "Screenshots" ? <ScreenshotPanel screenshots={proof.screenshots} /> : null}
          {activeTab === "Timeline" ? <TimelineFeed records={[proof]} onOpen={() => {}} /> : null}
          {activeTab === "Verification" ? (
            <div className="proof-audit-detail-grid">
              <div className="proof-audit-detail-card"><span>Status</span><b>{proof.verification_status}</b></div>
              <div className="proof-audit-detail-card"><span>Required</span><b>{proof.verification_required ? "Yes" : "No"}</b></div>
              <div className="proof-audit-detail-wide"><h3>Operator Notes</h3><p>{proof.operator_notes.length ? proof.operator_notes.join(" | ") : "No operator notes recorded."}</p></div>
            </div>
          ) : null}
          {activeTab === "Audit" ? (
            <div className="proof-audit-risk-list">
              {(proof.audit_flags.length ? proof.audit_flags : ["No audit flags detected."]).map((flag, index) => <p className="proof-audit-risk" key={`audit-${flag}-${index}`}>{flag}</p>)}
            </div>
          ) : null}
          {activeTab === "Risks" ? (
            <div className="proof-audit-risk-list">
              {(proof.blockers.length ? proof.blockers : ["No hard blockers detected."]).map((blocker, index) => <p className="proof-audit-risk blocker" key={`blocker-${blocker}-${index}`}>{blocker}</p>)}
              {proof.risks.map((risk, index) => <p className="proof-audit-risk" key={`risk-${risk}-${index}`}>{risk}</p>)}
            </div>
          ) : null}
          <p className="proof-audit-safety-note">Local review state only. This workspace cannot send email, upload to a portal, or perform final submit.</p>
        </div>
      </aside>
    </div>
  );
}

function PanelShell({ title, icon: Icon, children }) {
  return (
    <div className="proof-audit-panel card">
      <div className="proof-audit-panel-head">
        <h3>{Icon ? <Icon size={16} /> : null}{title}</h3>
      </div>
      {children}
    </div>
  );
}

export default function ProofAuditCentreWorkspace() {
  const [endpointState, setEndpointState] = useState({ loading: true, results: [], error: "" });
  const [proofs, setProofs] = useState([]);
  const [query, setQuery] = useState("");
  const [province, setProvince] = useState("All");
  const [proofStatus, setProofStatus] = useState("All");
  const [verificationRequired, setVerificationRequired] = useState("All");
  const [blockersOnly, setBlockersOnly] = useState(false);
  const [portal, setPortal] = useState("All");
  const [recentActivity, setRecentActivity] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [activeTab, setActiveTab] = useState("Overview");
  const [operatorState, setOperatorState] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadProofs() {
      setEndpointState((prev) => ({ ...prev, loading: true, error: "" }));
      const results = await Promise.all(PROOF_ENDPOINTS.map((path) => fetchEndpoint(path)));
      if (cancelled) return;

      const records = results
        .filter((result) => result.ok)
        .flatMap((result) => collectObjectRecords(result.data, result.path))
        .map((record) => normalizeProofRecord(record, record._sourcePath));

      const merged = mergeProofs(records).filter((proof) => proof.rfq_reference !== "RFQ" || proof.title !== "RFQ");
      setProofs(merged.length ? merged : DEMO_PROOFS);
      setEndpointState({
        loading: false,
        results,
        error: results.some((result) => result.ok) ? "" : "No proof endpoints responded with usable data.",
      });
    }

    loadProofs();
    return () => {
      cancelled = true;
    };
  }, []);

  const proofStatuses = useMemo(() => ["All", ...uniqueBy(proofs.map((proof) => proof.proof_status), (item) => item).filter(Boolean)], [proofs]);
  const portals = useMemo(() => ["All", ...uniqueBy(proofs.map((proof) => proof.portal), (item) => item).filter(Boolean)], [proofs]);
  const selectedProof = useMemo(() => proofs.find((proof) => proof.id === selectedId), [proofs, selectedId]);

  const filteredProofs = useMemo(() => {
    const term = query.trim().toLowerCase();
    return proofs.filter((proof) => {
      const haystack = `${proof.rfq_reference} ${proof.title} ${proof.buyer} ${proof.portal} ${proof.proof_status}`.toLowerCase();
      return (
        (!term || haystack.includes(term)) &&
        (province === "All" || proof.province === province) &&
        (proofStatus === "All" || proof.proof_status === proofStatus) &&
        (verificationRequired === "All" || (verificationRequired === "Required" ? proof.verification_required : !proof.verification_required)) &&
        (!blockersOnly || proof.blockers.length > 0) &&
        (portal === "All" || proof.portal === portal) &&
        recentMatch(proof, recentActivity)
      );
    });
  }, [blockersOnly, portal, proofStatus, proofs, province, query, recentActivity, verificationRequired]);

  const summary = useMemo(() => ({
    total: proofs.length,
    verified: proofs.filter((proof) => proof.verification_status === "Verified").length,
    review: proofs.filter((proof) => proof.verification_required || proof.verification_status === "Review Required").length,
    blocked: proofs.filter((proof) => proof.blockers.length > 0 || proof.proof_status === "Blocked").length,
  }), [proofs]);

  const focusedProof = selectedProof || filteredProofs[0] || proofs[0] || DEMO_PROOFS[0];
  const liveCount = endpointState.results.filter((result) => result.ok).length;
  const usingDemo = proofs.some((proof) => proof._demo);
  const healthResult = endpointState.results.find((result) => result.path === "/proof-center/health" && result.ok);

  function openProof(proof) {
    setSelectedId(proof.id);
    setActiveTab("Overview");
  }

  function setLocalAction(id, action) {
    setOperatorState((prev) => ({ ...prev, [id]: action }));
  }

  return (
    <section className="proof-audit-workspace" id="proof-audit-centre">
      <div className="proof-audit-hero card">
        <div>
          <p className="eyebrow">Proof & Audit Centre</p>
          <h1>Proof & Audit Centre Workspace</h1>
          <p className="muted">Read-only proof verification and audit traceability view probing {API_BASE}.</p>
        </div>
        <div className="proof-audit-endpoint-status">
          <span>{endpointState.loading ? "Loading" : `${liveCount}/${PROOF_ENDPOINTS.length} endpoints live`}</span>
          {usingDemo ? <b>Fallback data</b> : <b>Live data</b>}
        </div>
      </div>

      <div className="proof-audit-summary-grid">
        <div className="proof-audit-summary-card"><span>Proof Records</span><b>{summary.total}</b></div>
        <div className="proof-audit-summary-card good"><span>Verified</span><b>{summary.verified}</b></div>
        <div className="proof-audit-summary-card amber"><span>Review Required</span><b>{summary.review}</b></div>
        <div className="proof-audit-summary-card bad"><span>Blocked</span><b>{summary.blocked}</b></div>
      </div>

      <div className="proof-audit-toolbar card">
        <label className="proof-audit-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search RFQ, buyer, portal" /></label>
        <label><Filter size={15} /><select value={province} onChange={(event) => setProvince(event.target.value)}>{PROVINCES.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={proofStatus} onChange={(event) => setProofStatus(event.target.value)}>{proofStatuses.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={verificationRequired} onChange={(event) => setVerificationRequired(event.target.value)}>{["All", "Required", "Not Required"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={portal} onChange={(event) => setPortal(event.target.value)}>{portals.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label><Filter size={15} /><select value={recentActivity} onChange={(event) => setRecentActivity(event.target.value)}>{["All", "24h", "7d", "30d"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <button className={blockersOnly ? "active" : ""} type="button" onClick={() => setBlockersOnly((value) => !value)}><ShieldAlert size={15} />Blockers only</button>
      </div>

      {endpointState.error ? <div className="proof-audit-warning"><AlertTriangle size={16} />{endpointState.error}</div> : null}
      {usingDemo ? <div className="proof-audit-warning"><FileCheck2 size={16} />No live proof rows were found. Showing a non-destructive workspace preview row.</div> : null}

      <div className="proof-audit-layout">
        <PanelShell title="Proof Timeline Feed" icon={History}>
          <TimelineFeed records={filteredProofs} onOpen={openProof} />
        </PanelShell>

        <PanelShell title="Verification Queue" icon={ShieldCheck}>
          <div className="proof-verification-list">
            {filteredProofs.filter((proof) => proof.verification_required || proof.verification_status !== "Verified").slice(0, 12).map((proof, index) => (
              <button type="button" key={`${proof.id}-${index}`} onClick={() => openProof(proof)}>
                <StatusChip label="Verification" status={proof.verification_status} />
                <div><b>{proof.rfq_reference}</b><span>{proof.buyer}</span></div>
              </button>
            ))}
            {!filteredProofs.some((proof) => proof.verification_required || proof.verification_status !== "Verified") ? <div className="proof-audit-empty-inline">No verification queue items.</div> : null}
          </div>
        </PanelShell>
      </div>

      <div className="proof-audit-panels">
        <PanelShell title="Screenshot Proof Panel" icon={Image}>
          <ScreenshotPanel screenshots={focusedProof.screenshots} />
        </PanelShell>
        <PanelShell title="Proof Files Panel" icon={FileArchive}>
          <ProofFileList items={focusedProof.proof_files} empty="No proof files detected for the focused record." />
        </PanelShell>
        <PanelShell title="Audit Flags / Risks" icon={Flag}>
          <div className="proof-audit-risk-list">
            {(focusedProof.audit_flags.length ? focusedProof.audit_flags : ["No audit flags detected."]).map((flag, index) => <p className="proof-audit-risk" key={`flag-${flag}-${index}`}>{flag}</p>)}
            {focusedProof.risks.map((risk, index) => <p className="proof-audit-risk" key={`risk-${risk}-${index}`}>{risk}</p>)}
          </div>
        </PanelShell>
        <PanelShell title="Proof Centre Health" icon={ShieldCheck}>
          <div className="proof-audit-health-grid">
            <div><span>Endpoint</span><b>{healthResult ? "Live" : "Fallback"}</b></div>
            <div><span>Records</span><b>{summary.total}</b></div>
            <div><span>Verified</span><b>{summary.verified}</b></div>
            <div><span>Review</span><b>{summary.review}</b></div>
          </div>
        </PanelShell>
        <PanelShell title="Submission Traceability" icon={FileCheck2}>
          <div className="proof-trace-list">
            {focusedProof.timeline.map((event, index) => (
              <div key={`${event.state}-${event.timestamp}-${index}`}>
                <TimelineChip state={event.state} />
                <b>{event.label}</b>
                <span>{formatDateTime(event.timestamp)}</span>
              </div>
            ))}
          </div>
        </PanelShell>
      </div>

      <DetailDrawer
        proof={selectedProof}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onClose={() => setSelectedId("")}
        operatorState={operatorState}
        onOperatorAction={setLocalAction}
      />
    </section>
  );
}
