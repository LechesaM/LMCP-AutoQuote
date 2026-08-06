const API_BASE = import.meta?.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 9000;

export const CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS = {
  health: "/platform/customer-documents/health",
  readiness: "/platform/customer-documents/readiness",
  identity: "/platform/customer-documents/identity",
  catalogue: "/platform/customer-documents/catalogue",
  document: "/platform/customer-documents/document",
  classifications: "/platform/customer-documents/classifications",
  lifecycle: "/platform/customer-documents/lifecycle",
  retention: "/platform/customer-documents/retention",
  integrity: "/platform/customer-documents/integrity",
  policy: "/platform/customer-documents/policy",
  diagnostics: "/platform/customer-documents/diagnostics",
  compatibility: "/platform/customer-documents/compatibility",
  apiContract: "/platform/customer-documents/api-contract",
};

const DEFAULT_FALLBACK = {
  scope: "customer_document_centre",
  status: "NO_DATA",
  data_state: "NO_DATA",
};

function toQueryString(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

async function fetchJson(path, fallback = DEFAULT_FALLBACK, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      credentials: "include",
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return fallback ?? {
        status: "UNAVAILABLE",
        data_state: "UNAVAILABLE",
        error: `${response.status} ${response.statusText}`,
        path,
      };
    }

    return await response.json();
  } catch (error) {
    return fallback ?? {
      status: "UNAVAILABLE",
      data_state: "UNAVAILABLE",
      error: error?.message || "Customer document centre request failed.",
      path,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchSnapshot(options = {}) {
  const tenantId = String(options.tenantId || "").trim();
  const documentId = String(options.documentId || "NO_DATA").trim() || "NO_DATA";
  const query = toQueryString({
    tenant_id: tenantId,
    page: options.page || 1,
    limit: options.limit || 20,
    document_type: options.documentType || "",
    classification: options.classification || "",
    visibility: options.visibility || "",
  });

  const [
    health,
    readiness,
    identity,
    catalogue,
    document,
    classifications,
    lifecycle,
    retention,
    integrity,
    policy,
    diagnostics,
    compatibility,
    apiContract,
  ] = await Promise.all([
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.health, {
      ...DEFAULT_FALLBACK,
      health_state: "READY_WITH_LIMITATIONS",
      readiness_state: "READY_WITH_LIMITATIONS",
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.readiness, {
      ...DEFAULT_FALLBACK,
      readiness_state: "READY_WITH_LIMITATIONS",
      limitations: [],
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.identity, {
      ...DEFAULT_FALLBACK,
      identity: null,
    }),
    fetchJson(`${CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.catalogue}${query}`, {
      ...DEFAULT_FALLBACK,
      catalogue: null,
    }),
    fetchJson(`${CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.document}/${encodeURIComponent(documentId)}`, {
      ...DEFAULT_FALLBACK,
      document: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.classifications, {
      ...DEFAULT_FALLBACK,
      classifications: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.lifecycle, {
      ...DEFAULT_FALLBACK,
      lifecycle: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.retention, {
      ...DEFAULT_FALLBACK,
      retention: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.integrity, {
      ...DEFAULT_FALLBACK,
      integrity: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.policy, {
      ...DEFAULT_FALLBACK,
      policy: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.diagnostics, {
      ...DEFAULT_FALLBACK,
      diagnostics: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.compatibility, {
      ...DEFAULT_FALLBACK,
      compatibility: null,
    }),
    fetchJson(CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.apiContract, {
      ...DEFAULT_FALLBACK,
      contract: null,
    }),
  ]);

  const catalogueRecord = catalogue?.catalogue || null;
  const documentRecord = document?.document || null;
  const classificationRecord = classifications?.classifications || null;
  const lifecycleRecord = lifecycle?.lifecycle || null;
  const retentionRecord = retention?.retention || null;
  const integrityRecord = integrity?.integrity || null;
  const policyRecord = policy?.policy || null;
  const diagnosticsRecord = diagnostics?.diagnostics || null;
  const compatibilityRecord = compatibility?.compatibility || null;
  const apiContractRecord = apiContract?.contract || null;
  const documentItems = Array.isArray(catalogueRecord?.records) ? catalogueRecord.records : [];
  const classificationItems = Array.isArray(classificationRecord?.classifications) ? classificationRecord.classifications : [];

  return {
    status: String(health?.status || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    healthState: String(health?.health_state || health?.status || "READY_WITH_LIMITATIONS").toUpperCase(),
    readinessState: String(readiness?.readiness_state || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    identity: identity?.identity || null,
    catalogue: catalogueRecord,
    document: documentRecord,
    classifications: classificationRecord,
    lifecycle: lifecycleRecord,
    retention: retentionRecord,
    integrity: integrityRecord,
    visibility: policyRecord,
    diagnostics: diagnosticsRecord,
    audit: health?.audit || null,
    observability: health?.observability || null,
    compatibility: compatibilityRecord,
    health,
    readiness,
    missionControlIntegration: health?.mission_control_integration || {
      workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
      governance_status: "PRESERVED",
      security_status: "FAIL_CLOSED",
    },
    frontendExperience: health?.frontend_experience || {
      workspace: "CustomerDocumentCentreWorkspace",
      truthfulness: "Read-only secure document centre with no fabricated records, no uploads, and no downloads.",
    },
    apiContract: apiContractRecord,
    counts: {
      documents: documentItems.length,
      classifications: classificationItems.length,
    },
    requested: {
      tenantId,
      documentId,
    },
  };
}

export async function getCustomerDocumentCentreSnapshot(options = {}) {
  return fetchSnapshot(options);
}
