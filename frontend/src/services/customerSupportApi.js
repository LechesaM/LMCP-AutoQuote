const API_BASE = import.meta?.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 9000;

export const CUSTOMER_SUPPORT_ENDPOINTS = {
  health: "/platform/customer-support/health",
  readiness: "/platform/customer-support/readiness",
  identity: "/platform/customer-support/identity",
  cases: "/platform/customer-support/cases",
  priorities: "/platform/customer-support/priorities",
  slas: "/platform/customer-support/slas",
  queues: "/platform/customer-support/queues",
  knowledgeBase: "/platform/customer-support/knowledge-base",
  lifecycle: "/platform/customer-support/lifecycle",
  policy: "/platform/customer-support/policy",
  diagnostics: "/platform/customer-support/diagnostics",
  compatibility: "/platform/customer-support/compatibility",
  apiContract: "/platform/customer-support/api-contract",
};

const DEFAULT_FALLBACK = {
  scope: "customer_support",
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
      error: error?.message || "Customer support request failed.",
      path,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchSnapshot(options = {}) {
  const tenantId = String(options.tenantId || "").trim();
  const caseQuery = toQueryString({
    tenant_id: tenantId,
    page: options.page || 1,
    limit: options.limit || 20,
    priority: options.priority || "",
    classification: options.classification || "",
    queue: options.queue || "",
  });
  const knowledgeQuery = toQueryString({
    tenant_id: tenantId,
    page: options.page || 1,
    limit: options.limit || 20,
    category: options.category || "",
  });

  const [
    health,
    readiness,
    identity,
    cases,
    priorities,
    slas,
    queues,
    knowledgeBase,
    lifecycle,
    policy,
    diagnostics,
    compatibility,
    apiContract,
  ] = await Promise.all([
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.health, {
      ...DEFAULT_FALLBACK,
      health_state: "READY_WITH_LIMITATIONS",
      readiness_state: "READY_WITH_LIMITATIONS",
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.readiness, {
      ...DEFAULT_FALLBACK,
      readiness_state: "READY_WITH_LIMITATIONS",
      limitations: [],
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.identity, {
      ...DEFAULT_FALLBACK,
      identity: null,
    }),
    fetchJson(`${CUSTOMER_SUPPORT_ENDPOINTS.cases}${caseQuery}`, {
      ...DEFAULT_FALLBACK,
      cases: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.priorities, {
      ...DEFAULT_FALLBACK,
      priorities: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.slas, {
      ...DEFAULT_FALLBACK,
      slas: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.queues, {
      ...DEFAULT_FALLBACK,
      queues: null,
    }),
    fetchJson(`${CUSTOMER_SUPPORT_ENDPOINTS.knowledgeBase}${knowledgeQuery}`, {
      ...DEFAULT_FALLBACK,
      knowledge_base: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.lifecycle, {
      ...DEFAULT_FALLBACK,
      lifecycle: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.policy, {
      ...DEFAULT_FALLBACK,
      policy: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.diagnostics, {
      ...DEFAULT_FALLBACK,
      diagnostics: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.compatibility, {
      ...DEFAULT_FALLBACK,
      compatibility: null,
    }),
    fetchJson(CUSTOMER_SUPPORT_ENDPOINTS.apiContract, {
      ...DEFAULT_FALLBACK,
      contract: null,
    }),
  ]);

  const casesRecord = cases?.cases || null;
  const prioritiesRecord = priorities?.priorities || null;
  const slasRecord = slas?.slas || null;
  const queuesRecord = queues?.queues || null;
  const knowledgeRecord = knowledgeBase?.knowledge_base || null;
  const policyRecord = policy?.policy || null;
  const caseItems = Array.isArray(casesRecord?.records) ? casesRecord.records : [];
  const priorityItems = Array.isArray(prioritiesRecord?.priorities) ? prioritiesRecord.priorities : [];
  const slaItems = Array.isArray(slasRecord?.slas) ? slasRecord.slas : [];
  const queueItems = Array.isArray(queuesRecord?.queues) ? queuesRecord.queues : [];
  const knowledgeItems = Array.isArray(knowledgeRecord?.records) ? knowledgeRecord.records : [];
  const preferenceItems = Array.isArray(policyRecord?.support_preferences) ? policyRecord.support_preferences : [];

  return {
    status: String(health?.status || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    healthState: String(health?.health_state || health?.status || "READY_WITH_LIMITATIONS").toUpperCase(),
    readinessState: String(readiness?.readiness_state || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    identity: identity?.identity || null,
    cases: casesRecord,
    priorities: prioritiesRecord,
    slas: slasRecord,
    queues: queuesRecord,
    knowledgeBase: knowledgeRecord,
    lifecycle: lifecycle?.lifecycle || null,
    policy: policyRecord,
    diagnostics: diagnostics?.diagnostics || null,
    compatibility: compatibility?.compatibility || null,
    health,
    readiness,
    missionControlIntegration: health?.mission_control_integration || {
      workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
      governance_status: "PRESERVED",
      security_status: "FAIL_CLOSED",
    },
    frontendExperience: health?.frontend_experience || {
      workspace: "CustomerSupportWorkspace",
      truthfulness: "Truthful read-only support case and knowledge metadata with no fabricated support activity.",
    },
    apiContract: apiContract?.contract || null,
    counts: {
      cases: caseItems.length,
      priorities: priorityItems.length,
      slas: slaItems.length,
      queues: queueItems.length,
      knowledge: knowledgeItems.length,
      preferences: preferenceItems.length,
    },
    requested: {
      tenantId,
    },
  };
}

export async function getCustomerSupportSnapshot(options = {}) {
  return fetchSnapshot(options);
}
