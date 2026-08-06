const API_BASE = import.meta?.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 9000;

export const CUSTOMER_COMMUNICATION_ENDPOINTS = {
  health: "/platform/customer-communication/health",
  readiness: "/platform/customer-communication/readiness",
  identity: "/platform/customer-communication/identity",
  registry: "/platform/customer-communication/registry",
  catalogue: "/platform/customer-communication/catalogue",
  templates: "/platform/customer-communication/templates",
  preferences: "/platform/customer-communication/preferences",
  lifecycle: "/platform/customer-communication/lifecycle",
  delivery: "/platform/customer-communication/delivery",
  policy: "/platform/customer-communication/policy",
  diagnostics: "/platform/customer-communication/diagnostics",
  compatibility: "/platform/customer-communication/compatibility",
  apiContract: "/platform/customer-communication/api-contract",
};

const DEFAULT_FALLBACK = {
  scope: "customer_communication",
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
      error: error?.message || "Customer communication request failed.",
      path,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchSnapshot(options = {}) {
  const tenantId = String(options.tenantId || "").trim();
  const query = toQueryString({
    tenant_id: tenantId,
    page: options.page || 1,
    limit: options.limit || 20,
    notification_type: options.notificationType || "",
    classification: options.classification || "",
    channel: options.channel || "",
  });

  const [
    health,
    readiness,
    identity,
    registry,
    catalogue,
    templates,
    preferences,
    lifecycle,
    delivery,
    policy,
    diagnostics,
    compatibility,
    apiContract,
  ] = await Promise.all([
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.health, {
      ...DEFAULT_FALLBACK,
      health_state: "READY_WITH_LIMITATIONS",
      readiness_state: "READY_WITH_LIMITATIONS",
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.readiness, {
      ...DEFAULT_FALLBACK,
      readiness_state: "READY_WITH_LIMITATIONS",
      limitations: [],
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.identity, {
      ...DEFAULT_FALLBACK,
      identity: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.registry, {
      ...DEFAULT_FALLBACK,
      registry: null,
    }),
    fetchJson(`${CUSTOMER_COMMUNICATION_ENDPOINTS.catalogue}${query}`, {
      ...DEFAULT_FALLBACK,
      catalogue: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.templates, {
      ...DEFAULT_FALLBACK,
      templates: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.preferences, {
      ...DEFAULT_FALLBACK,
      preferences: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.lifecycle, {
      ...DEFAULT_FALLBACK,
      lifecycle: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.delivery, {
      ...DEFAULT_FALLBACK,
      delivery: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.policy, {
      ...DEFAULT_FALLBACK,
      policy: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.diagnostics, {
      ...DEFAULT_FALLBACK,
      diagnostics: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.compatibility, {
      ...DEFAULT_FALLBACK,
      compatibility: null,
    }),
    fetchJson(CUSTOMER_COMMUNICATION_ENDPOINTS.apiContract, {
      ...DEFAULT_FALLBACK,
      contract: null,
    }),
  ]);

  const registryRecord = registry?.registry || null;
  const catalogueRecord = catalogue?.catalogue || null;
  const templatesRecord = templates?.templates || null;
  const preferencesRecord = preferences?.preferences || null;
  const deliveryRecord = delivery?.delivery || null;
  const registryItems = Array.isArray(registryRecord?.records) ? registryRecord.records : [];
  const catalogueItems = Array.isArray(catalogueRecord?.records) ? catalogueRecord.records : [];
  const templateItems = Array.isArray(templatesRecord?.templates) ? templatesRecord.templates : [];
  const preferenceItems = Array.isArray(preferencesRecord?.channels) ? preferencesRecord.channels : [];
  const deliveryItems = Array.isArray(deliveryRecord?.delivery_records) ? deliveryRecord.delivery_records : [];

  return {
    status: String(health?.status || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    healthState: String(health?.health_state || health?.status || "READY_WITH_LIMITATIONS").toUpperCase(),
    readinessState: String(readiness?.readiness_state || health?.readiness_state || "READY_WITH_LIMITATIONS").toUpperCase(),
    identity: identity?.identity || null,
    registry: registryRecord,
    catalogue: catalogueRecord,
    templates: templatesRecord,
    preferences: preferencesRecord,
    delivery: deliveryRecord,
    lifecycle: lifecycle?.lifecycle || null,
    policy: policy?.policy || null,
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
      workspace: "CustomerCommunicationWorkspace",
      truthfulness: "Truthful read-only communication and notifications metadata with no fabricated communication events.",
    },
    apiContract: apiContract?.contract || null,
    counts: {
      notifications: registryItems.length,
      catalogue: catalogueItems.length,
      templates: templateItems.length,
      preferences: preferenceItems.length,
      deliveries: deliveryItems.length,
    },
    requested: {
      tenantId,
    },
  };
}

export async function getCustomerCommunicationSnapshot(options = {}) {
  return fetchSnapshot(options);
}
