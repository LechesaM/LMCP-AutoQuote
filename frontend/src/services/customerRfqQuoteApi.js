const API_BASE = import.meta?.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 9000;

export const CUSTOMER_RFQ_QUOTE_ENDPOINTS = {
  health: "/platform/customer-rfq-quotes/health",
  readiness: "/platform/customer-rfq-quotes/readiness",
  identity: "/platform/customer-rfq-quotes/identity",
  rfqs: "/platform/customer-rfq-quotes/rfqs",
  quotations: "/platform/customer-rfq-quotes/quotations",
  rfqLifecycle: "/platform/customer-rfq-quotes/rfq-lifecycle",
  quotationLifecycle: "/platform/customer-rfq-quotes/quotation-lifecycle",
  sourceAuthority: "/platform/customer-rfq-quotes/source-authority",
  freshness: "/platform/customer-rfq-quotes/freshness",
  policy: "/platform/customer-rfq-quotes/policy",
  diagnostics: "/platform/customer-rfq-quotes/diagnostics",
  compatibility: "/platform/customer-rfq-quotes/compatibility",
  apiContract: "/platform/customer-rfq-quotes/api-contract",
};

const DEFAULT_FALLBACK = {
  scope: "customer_rfq_quote_workspace",
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
      headers: {
        Accept: "application/json",
      },
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
      error: error?.message || "Customer RFQ and quote workspace request failed.",
      path,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchSnapshot(options = {}) {
  const tenantId = String(options.tenantId || "").trim();
  const rfqReference = String(options.rfqReference || "").trim();
  const quotationReference = String(options.quotationReference || "").trim();
  const query = toQueryString({
    tenant_id: tenantId,
    page: options.page || 1,
    limit: options.limit || 20,
    status: options.status || "",
    query: options.query || "",
  });

  const [
    health,
    readiness,
    identity,
    rfqs,
    quotations,
    rfqLifecycle,
    quotationLifecycle,
    sourceAuthority,
    freshness,
    policy,
    diagnostics,
    compatibility,
    apiContract,
  ] = await Promise.all([
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.health, {
      ...DEFAULT_FALLBACK,
      health_state: "READY_WITH_LIMITATIONS",
      readiness_state: "READY_WITH_LIMITATIONS",
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.readiness, {
      ...DEFAULT_FALLBACK,
      readiness_state: "READY_WITH_LIMITATIONS",
      limitations: [],
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.identity, {
      ...DEFAULT_FALLBACK,
      identity: null,
    }),
    fetchJson(`${CUSTOMER_RFQ_QUOTE_ENDPOINTS.rfqs}${query}`, {
      ...DEFAULT_FALLBACK,
      rfqs: null,
    }),
    fetchJson(`${CUSTOMER_RFQ_QUOTE_ENDPOINTS.quotations}${query}`, {
      ...DEFAULT_FALLBACK,
      quotations: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.rfqLifecycle, {
      ...DEFAULT_FALLBACK,
      lifecycle: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.quotationLifecycle, {
      ...DEFAULT_FALLBACK,
      lifecycle: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.sourceAuthority, {
      ...DEFAULT_FALLBACK,
      source_authority: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.freshness, {
      ...DEFAULT_FALLBACK,
      freshness: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.policy, {
      ...DEFAULT_FALLBACK,
      policy: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.diagnostics, {
      ...DEFAULT_FALLBACK,
      diagnostics: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.compatibility, {
      ...DEFAULT_FALLBACK,
      compatibility: null,
    }),
    fetchJson(CUSTOMER_RFQ_QUOTE_ENDPOINTS.apiContract, {
      ...DEFAULT_FALLBACK,
      contract: null,
    }),
  ]);

  const rfqRecord = rfqs?.rfqs || null;
  const quotationRecord = quotations?.quotations || null;
  const rfqItems = Array.isArray(rfqRecord?.records) ? rfqRecord.records : [];
  const quotationItems = Array.isArray(quotationRecord?.records) ? quotationRecord.records : [];
  const identityRecord = identity?.identity || null;
  const rfqLifecycleRecord = rfqLifecycle?.lifecycle || null;
  const quotationLifecycleRecord = quotationLifecycle?.lifecycle || null;
  const sourceAuthorityRecord = sourceAuthority?.source_authority || null;
  const freshnessRecord = freshness?.freshness || null;
  const policyRecord = policy?.policy || null;
  const diagnosticsRecord = diagnostics?.diagnostics || null;
  const compatibilityRecord = compatibility?.compatibility || null;
  const apiContractRecord = apiContract?.contract || null;

  return {
    status: String(health?.status || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    healthState: String(health?.health_state || health?.status || "READY_WITH_LIMITATIONS").toUpperCase(),
    readinessState: String(readiness?.readiness_state || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    identity: identityRecord,
    rfqs: rfqRecord,
    quotations: quotationRecord,
    rfqLifecycle: rfqLifecycleRecord,
    quotationLifecycle: quotationLifecycleRecord,
    sourceAuthority: sourceAuthorityRecord,
    freshness: freshnessRecord,
    policy: policyRecord,
    diagnostics: diagnosticsRecord,
    compatibility: compatibilityRecord,
    health,
    readiness,
    missionControlIntegration: health?.mission_control_integration || {
      workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
      governance_status: "PRESERVED",
      security_status: "FAIL_CLOSED",
    },
    frontendExperience: health?.frontend_experience || {
      workspace: "CustomerRfqQuoteWorkspace",
      truthfulness: "Read-only RFQ and quotation workspace with no fabricated records, no uploads, and no submit controls.",
    },
    apiContract: apiContractRecord,
    counts: {
      rfqs: rfqItems.length,
      quotations: quotationItems.length,
    },
    requested: {
      tenantId,
      rfqReference,
      quotationReference,
    },
  };
}

export async function getCustomerRfqQuoteWorkspaceSnapshot(options = {}) {
  return fetchSnapshot(options);
}
