import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  CUSTOMER_RFQ_QUOTE_ENDPOINTS,
  getCustomerRfqQuoteWorkspaceSnapshot,
} from "../src/services/customerRfqQuoteApi.js";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const missionSource = readFileSync(new URL("../src/components/MissionControlLanding.jsx", import.meta.url), "utf8");
const workspaceSource = readFileSync(new URL("../src/components/CustomerRfqQuoteWorkspace.jsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/services/customerRfqQuoteApi.js", import.meta.url), "utf8");

test("customer RFQ and quote workspace snapshot is read-only and namespaced", async () => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), options });
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const base = {
      status: "READY_WITH_LIMITATIONS",
      scope: "customer_rfq_quote_workspace",
      data_state: "NO_DATA",
    };

    const payloads = {
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.health]: {
        ...base,
        health_state: "READY_WITH_LIMITATIONS",
        readiness_state: "READY_WITH_LIMITATIONS",
        mission_control_integration: {
          workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
          governance_status: "PRESERVED",
          security_status: "FAIL_CLOSED",
          visible_rfq_count: 0,
          visible_quotation_count: 0,
        },
        frontend_experience: {
          workspace: "CustomerRfqQuoteWorkspace",
          truthfulness: "Read-only RFQ and quotation workspace with no fabricated records, no uploads, and no submit controls.",
        },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.readiness]: { ...base, readiness_state: "READY_WITH_LIMITATIONS", limitations: ["RFQ and quotation workspace remains read only."] },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.identity]: {
        ...base,
        identity: {
          workspace_id: "LMCP-RFQ-65-6-4",
          canonical_name: "LMCP AutoQuote RFQ & Quote Workspace",
          portal_reference: "PHASE65_6_1_IMPLEMENTATION_COMPLETE",
          dashboard_reference: "PHASE65_6_3_IMPLEMENTATION_COMPLETE",
          identity_reference: "PHASE65_6_2_IMPLEMENTATION_COMPLETE",
          lifecycle_state: "READY_WITH_LIMITATIONS",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          accepted_limitations: ["RFQ and quotation workspace is read only."],
        },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.rfqs]: {
        ...base,
        rfqs: {
          registry_state: "NO_DATA",
          record_label: "RFQ",
          records: [],
          summary: { record_count: 0, visible_count: 0, active_count: 0, review_required_count: 0, closed_count: 0 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "TENANT_CONTEXT_REQUIRED",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          permitted_filters: ["tenant_id", "status", "query", "page", "limit"],
          permitted_sort_fields: ["issue_date", "closing_date", "lifecycle_state", "rfq_reference"],
        },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.quotations]: {
        ...base,
        quotations: {
          registry_state: "NO_DATA",
          record_label: "Quotation",
          records: [],
          summary: { record_count: 0, visible_count: 0, active_count: 0, review_required_count: 0, closed_count: 0 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "TENANT_CONTEXT_REQUIRED",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          permitted_filters: ["tenant_id", "status", "query", "page", "limit"],
          permitted_sort_fields: ["prepared_date", "lifecycle_state", "quotation_reference"],
        },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.rfqLifecycle]: {
        ...base,
        lifecycle: { lifecycle_state: "NO_DATA", no_mutation_guarantee: true, visible_states: ["NO_DATA", "FAILED_CLOSED"] },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.quotationLifecycle]: {
        ...base,
        lifecycle: { lifecycle_state: "NO_DATA", no_mutation_guarantee: true, visible_states: ["NO_DATA", "FAILED_CLOSED"] },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.sourceAuthority]: {
        ...base,
        source_authority: { authority_state: "NO_DATA", source_system: "RFQ lifecycle and quote draft metadata" },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.freshness]: {
        ...base,
        freshness: { overall_freshness_state: "NO_DATA", stale_threshold: "24h" },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.policy]: {
        ...base,
        policy: { global_governance_precedence: "highest", external_action_prohibition: "denied", mutation_prohibition: "denied" },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.diagnostics]: {
        ...base,
        diagnostics: { diagnostic_state: "READY_WITH_LIMITATIONS", redaction_posture: "bounded", tenant_safe: true },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.compatibility]: {
        ...base,
        compatibility: { compatibility_state: "COMPATIBLE_WITH_LIMITATIONS", limitations: ["No customer workflow is implemented."] },
      },
      [CUSTOMER_RFQ_QUOTE_ENDPOINTS.apiContract]: {
        ...base,
        contract: {
          router: "customer-rfq-quotes",
          phase: "PHASE65.6.4",
          canonical_pdf: { match_status: "MATCH", observed_page_count: 28 },
          routes: [
            { path: "/platform/customer-rfq-quotes/health", method: "GET" },
            { path: "/platform/customer-rfq-quotes/readiness", method: "GET" },
            { path: "/platform/customer-rfq-quotes/identity", method: "GET" },
            { path: "/platform/customer-rfq-quotes/rfqs", method: "GET" },
            { path: "/platform/customer-rfq-quotes/rfqs/{rfq_reference}", method: "GET" },
            { path: "/platform/customer-rfq-quotes/quotations", method: "GET" },
            { path: "/platform/customer-rfq-quotes/quotations/{quotation_reference}", method: "GET" },
            { path: "/platform/customer-rfq-quotes/rfq-lifecycle", method: "GET" },
            { path: "/platform/customer-rfq-quotes/quotation-lifecycle", method: "GET" },
            { path: "/platform/customer-rfq-quotes/source-authority", method: "GET" },
            { path: "/platform/customer-rfq-quotes/freshness", method: "GET" },
            { path: "/platform/customer-rfq-quotes/policy", method: "GET" },
            { path: "/platform/customer-rfq-quotes/diagnostics", method: "GET" },
            { path: "/platform/customer-rfq-quotes/compatibility", method: "GET" },
            { path: "/platform/customer-rfq-quotes/api-contract", method: "GET" },
          ],
        },
      },
    };

    return {
      ok: true,
      json: async () => payloads[path] || base,
    };
  };

  try {
    const snapshot = await getCustomerRfqQuoteWorkspaceSnapshot();
    assert.equal(requests.length, 13);
    for (const request of requests) {
      assert.equal(request.options.method || "GET", "GET");
      assert.equal(request.options.credentials, "include");
      assert.ok(String(request.url).includes("/platform/customer-rfq-quotes/"));
    }
    assert.equal(snapshot.status, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.readinessState, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.counts.rfqs, 0);
    assert.equal(snapshot.counts.quotations, 0);
    assert.equal(snapshot.identity.workspace_id, "LMCP-RFQ-65-6-4");
    assert.equal(snapshot.missionControlIntegration.workspace_lifecycle_state, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.apiContract.router, "customer-rfq-quotes");
    assert.equal(snapshot.apiContract.canonical_pdf.match_status, "MATCH");
    assert.equal(snapshot.apiContract.routes.length, 15);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("customer RFQ and quote workspace source remains truthful", () => {
  assert.match(appSource, /RFQ & Quote Workspace/);
  assert.match(appSource, /CustomerRfqQuoteWorkspace/);
  assert.match(appSource, /getCustomerRfqQuoteWorkspaceSnapshot/);
  assert.match(appSource, /customer-rfq-quotes/);
  assert.match(missionSource, /Phase65\.6\.4 RFQ & Quote Workspace/);
  assert.match(missionSource, /customer-rfq-quotes/);
  assert.match(missionSource, /customer-rfq-quotes/);
  assert.match(workspaceSource, /Truthful read-only RFQ and quotation workspace/);
  assert.match(workspaceSource, /No fabricated RFQ or quotation data is shown\./);
  assert.match(apiSource, /CUSTOMER_RFQ_QUOTE_ENDPOINTS/);
  assert.match(apiSource, /getCustomerRfqQuoteWorkspaceSnapshot/);
  assert.match(apiSource, /credentials: "include"/);
  assert.match(apiSource, /\/platform\/customer-rfq-quotes\/api-contract/);
});
