import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS,
  getCustomerDocumentCentreSnapshot,
} from "../src/services/customerDocumentCentreApi.js";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const missionSource = readFileSync(new URL("../src/components/MissionControlLanding.jsx", import.meta.url), "utf8");
const workspaceSource = readFileSync(new URL("../src/components/CustomerDocumentCentreWorkspace.jsx", import.meta.url), "utf8");
const dashboardSource = readFileSync(new URL("../src/components/CustomerDashboardWorkspace.jsx", import.meta.url), "utf8");
const rfqSource = readFileSync(new URL("../src/components/CustomerRfqQuoteWorkspace.jsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/services/customerDocumentCentreApi.js", import.meta.url), "utf8");

test("customer document centre snapshot is read-only and namespaced", async () => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), options });
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const base = {
      status: "READY_WITH_LIMITATIONS",
      scope: "customer_document_centre",
      data_state: "NO_DATA",
    };

    const payloads = {
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.health]: {
        ...base,
        health_state: "READY_WITH_LIMITATIONS",
        readiness_state: "READY_WITH_LIMITATIONS",
        mission_control_integration: {
          workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
          governance_status: "PRESERVED",
          security_status: "FAIL_CLOSED",
          visible_document_count: 0,
          visible_catalogue_count: 0,
        },
        frontend_experience: {
          workspace: "CustomerDocumentCentreWorkspace",
          truthfulness: "Read-only secure document centre with no fabricated records, no uploads, and no downloads.",
        },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.readiness]: { ...base, readiness_state: "READY_WITH_LIMITATIONS", limitations: ["Secure document centre remains read only."] },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.identity]: {
        ...base,
        identity: {
          workspace_id: "LMCP-DOC-65-6-5",
          canonical_name: "LMCP AutoQuote Secure Document Centre",
          portal_reference: "PHASE65_6_1_IMPLEMENTATION_COMPLETE",
          dashboard_reference: "PHASE65_6_3_IMPLEMENTATION_COMPLETE",
          rfq_quote_reference: "PHASE65_6_4_IMPLEMENTATION_COMPLETE",
          lifecycle_state: "READY_WITH_LIMITATIONS",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          accepted_limitations: ["Secure document centre is read only."],
        },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.catalogue]: {
        ...base,
        catalogue: {
          registry_state: "NO_DATA",
          record_label: "Document",
          records: [],
          summary: { record_count: 0, visible_count: 0, downloadable_count: 0, uploadable_count: 0, shareable_count: 0 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "TENANT_CONTEXT_REQUIRED",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          permitted_filters: ["tenant_id", "document_type", "classification", "visibility", "page", "limit"],
          permitted_sort_fields: ["created_date", "updated_date", "document_name", "document_reference"],
        },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.document + "/NO_DATA"]: {
        ...base,
        document: {
          document_reference: "NO_DATA",
          document_name: "NO_DATA",
          tenant_reference: "TENANT_CONTEXT_REQUIRED",
          classification: "NO_DATA",
          visibility: "TENANT_CONTEXT_REQUIRED",
          integrity_status: "NO_DATA",
          checksum_available: false,
          download_available: false,
          upload_available: false,
          sharing_available: false,
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
        },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.classifications]: {
        ...base,
        classifications: {
          classification_state: "READY_WITH_LIMITATIONS",
          class_count: 3,
          classifications: [
            { classification_id: "TENANT_VISIBLE_METADATA", canonical_name: "Tenant Visible Metadata", trust_requirement: "tenant bound", visibility: "read only", storage_posture: "metadata only" },
            { classification_id: "CONFIDENTIAL_PROCUREMENT_METADATA", canonical_name: "Confidential Procurement Metadata", trust_requirement: "authorised tenant access", visibility: "read only", storage_posture: "metadata only" },
            { classification_id: "FAILED_CLOSED", canonical_name: "Failed Closed", trust_requirement: "deny by default", visibility: "blocked", storage_posture: "none" },
          ],
        },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.lifecycle]: {
        ...base,
        lifecycle: { lifecycle_state: "NO_DATA", no_mutation_guarantee: true, visible_states: ["NO_DATA", "FAILED_CLOSED"] },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.retention]: {
        ...base,
        retention: { retention_state: "NO_DATA", retention_policy: "metadata only", deletion_posture: "DENIED" },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.integrity]: {
        ...base,
        integrity: { integrity_state: "NO_DATA", checksum_algorithm: "SHA-256", checksum_available: false },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.policy]: {
        ...base,
        policy: { global_governance_precedence: "highest", external_action_prohibition: "denied", mutation_prohibition: "denied", download_prohibition: "denied", upload_prohibition: "denied", share_prohibition: "denied" },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.diagnostics]: {
        ...base,
        diagnostics: { diagnostic_state: "READY_WITH_LIMITATIONS", redaction_posture: "bounded", tenant_safe: true },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.compatibility]: {
        ...base,
        compatibility: { compatibility_state: "COMPATIBLE_WITH_LIMITATIONS", limitations: ["No storage provider integration is implemented."] },
      },
      [CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.apiContract]: {
        ...base,
        contract: {
          router: "customer-documents",
          phase: "PHASE65.6.5",
          canonical_pdf: { match_status: "MATCH", observed_page_count: 28 },
          routes: [
            { path: "/platform/customer-documents/health", method: "GET" },
            { path: "/platform/customer-documents/readiness", method: "GET" },
            { path: "/platform/customer-documents/identity", method: "GET" },
            { path: "/platform/customer-documents/catalogue", method: "GET" },
            { path: "/platform/customer-documents/document/{id}", method: "GET" },
            { path: "/platform/customer-documents/classifications", method: "GET" },
            { path: "/platform/customer-documents/lifecycle", method: "GET" },
            { path: "/platform/customer-documents/retention", method: "GET" },
            { path: "/platform/customer-documents/integrity", method: "GET" },
            { path: "/platform/customer-documents/policy", method: "GET" },
            { path: "/platform/customer-documents/diagnostics", method: "GET" },
            { path: "/platform/customer-documents/api-contract", method: "GET" },
            { path: "/platform/customer-documents/compatibility", method: "GET" },
          ],
        },
      },
    };

    return {
      ok: true,
      json: async () => payloads[path] || payloads[`${CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS.document}/NO_DATA`] || base,
    };
  };

  try {
    const snapshot = await getCustomerDocumentCentreSnapshot();
    assert.equal(requests.length, 13);
    for (const request of requests) {
      assert.equal(request.options.method || "GET", "GET");
      assert.equal(request.options.credentials, "include");
      assert.ok(String(request.url).includes("/platform/customer-documents/"));
    }
    assert.equal(snapshot.status, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.readinessState, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.counts.documents, 0);
    assert.equal(snapshot.counts.classifications, 3);
    assert.equal(snapshot.identity.workspace_id, "LMCP-DOC-65-6-5");
    assert.equal(snapshot.missionControlIntegration.workspace_lifecycle_state, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.apiContract.router, "customer-documents");
    assert.equal(snapshot.apiContract.canonical_pdf.match_status, "MATCH");
    assert.equal(snapshot.apiContract.routes.length, 13);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("customer document centre source remains truthful", () => {
  assert.match(appSource, /Secure Document Centre/);
  assert.match(appSource, /CustomerDocumentCentreWorkspace/);
  assert.match(appSource, /getCustomerDocumentCentreSnapshot/);
  assert.match(appSource, /customer-document-centre/);
  assert.match(missionSource, /Phase65\.6\.5 Secure Document Centre/);
  assert.match(missionSource, /customer-document-centre/);
  assert.match(workspaceSource, /Truthful read-only document centre foundation/);
  assert.match(workspaceSource, /No fabricated document data is shown\./);
  assert.match(workspaceSource, /No upload, download, delete, share, rename, move, sign, OCR, or indexing controls are implemented\./);
  assert.match(dashboardSource, /customer-document-centre/);
  assert.match(rfqSource, /customer-document-centre/);
  assert.match(apiSource, /CUSTOMER_DOCUMENT_CENTRE_ENDPOINTS/);
  assert.match(apiSource, /getCustomerDocumentCentreSnapshot/);
  assert.match(apiSource, /credentials: "include"/);
  assert.match(apiSource, /\/platform\/customer-documents\/api-contract/);
});

