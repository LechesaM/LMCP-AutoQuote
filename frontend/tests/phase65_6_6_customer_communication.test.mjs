import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  CUSTOMER_COMMUNICATION_ENDPOINTS,
  getCustomerCommunicationSnapshot,
} from "../src/services/customerCommunicationApi.js";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const missionSource = readFileSync(new URL("../src/components/MissionControlLanding.jsx", import.meta.url), "utf8");
const workspaceSource = readFileSync(new URL("../src/components/CustomerCommunicationWorkspace.jsx", import.meta.url), "utf8");
const dashboardSource = readFileSync(new URL("../src/components/CustomerDashboardWorkspace.jsx", import.meta.url), "utf8");
const documentSource = readFileSync(new URL("../src/components/CustomerDocumentCentreWorkspace.jsx", import.meta.url), "utf8");
const rfqSource = readFileSync(new URL("../src/components/CustomerRfqQuoteWorkspace.jsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/services/customerCommunicationApi.js", import.meta.url), "utf8");

test("customer communication snapshot is read-only and namespaced", async () => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), options });
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const base = {
      status: "READY_WITH_LIMITATIONS",
      scope: "customer_communication",
      data_state: "NO_DATA",
    };

    const payloads = {
      [CUSTOMER_COMMUNICATION_ENDPOINTS.health]: {
        ...base,
        health_state: "READY_WITH_LIMITATIONS",
        readiness_state: "READY_WITH_LIMITATIONS",
        mission_control_integration: {
          workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
          governance_status: "PRESERVED",
          security_status: "FAIL_CLOSED",
          visible_notification_count: 3,
          visible_template_count: 3,
          visible_preference_count: 7,
        },
        frontend_experience: {
          workspace: "CustomerCommunicationWorkspace",
          truthfulness: "Read-only communication and notifications metadata with no fabricated communication events.",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.readiness]: { ...base, readiness_state: "READY_WITH_LIMITATIONS", limitations: ["Communication centre remains read only."] },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.identity]: {
        ...base,
        identity: {
          workspace_id: "LMCP-COMM-65-6-6",
          canonical_name: "LMCP AutoQuote Communication & Notifications",
          portal_reference: "PHASE65_6_1_IMPLEMENTATION_COMPLETE",
          dashboard_reference: "PHASE65_6_3_IMPLEMENTATION_COMPLETE",
          rfq_quote_reference: "PHASE65_6_4_IMPLEMENTATION_COMPLETE",
          document_centre_reference: "PHASE65_6_5_IMPLEMENTATION_COMPLETE",
          lifecycle_state: "READY_WITH_LIMITATIONS",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          accepted_limitations: ["Communication centre is read only."],
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.registry]: {
        ...base,
        registry: {
          registry_state: "REGISTERED_METADATA_ONLY",
          record_label: "Notification",
          records: [
            { notification_reference: "portal-readiness-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "GOVERNANCE_NOTICE", source_authority: "Customer portal foundation metadata" },
            { notification_reference: "dashboard-summary-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "SUMMARY_NOTICE", source_authority: "Customer dashboard metadata" },
            { notification_reference: "workspace-guidance-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "GUIDANCE_NOTICE", source_authority: "Phase65 governance metadata" },
          ],
          summary: { record_count: 3, visible_count: 0, deliverable_count: 0, sendable_count: 0, scheduled_count: 0 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "READ_ONLY",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.catalogue]: {
        ...base,
        catalogue: {
          catalogue_state: "REGISTERED_METADATA_ONLY",
          record_label: "Notification",
          records: [
            { notification_reference: "portal-readiness-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "GOVERNANCE_NOTICE", source_authority: "Customer portal foundation metadata" },
            { notification_reference: "dashboard-summary-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "SUMMARY_NOTICE", source_authority: "Customer dashboard metadata" },
            { notification_reference: "workspace-guidance-notice", communication_channel: "portal", lifecycle: "NO_DATA", classification: "GUIDANCE_NOTICE", source_authority: "Phase65 governance metadata" },
          ],
          summary: { record_count: 3, visible_count: 0, deliverable_count: 0, template_count: 3 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "READ_ONLY",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.templates]: {
        ...base,
        templates: {
          template_state: "REGISTERED_METADATA_ONLY",
          record_label: "Template",
          templates: [
            { template_reference: "portal-readiness-template", canonical_name: "Portal Readiness Template", channel: "portal", classification: "GOVERNANCE_NOTICE" },
            { template_reference: "dashboard-summary-template", canonical_name: "Dashboard Summary Template", channel: "portal", classification: "SUMMARY_NOTICE" },
            { template_reference: "workspace-guidance-template", canonical_name: "Workspace Guidance Template", channel: "portal", classification: "GUIDANCE_NOTICE" },
          ],
          summary: { template_count: 3, renderable_count: 0, sendable_count: 0, scheduleable_count: 0 },
          source_authority_state: "NO_DATA",
          freshness_state: "NO_DATA",
          tenant_context_posture: "TENANT_CONTEXT_REQUIRED",
          visibility_state: "READ_ONLY",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.preferences]: {
        ...base,
        preferences: {
          preference_state: "REGISTERED_METADATA_ONLY",
          default_delivery_mode: "DRAFT_ONLY",
          channels: [
            { channel: "email", enabled: false, posture: "DRAFT_ONLY", send_allowed: false, schedule_allowed: false },
            { channel: "sms", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
            { channel: "whatsapp", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
            { channel: "teams", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
            { channel: "slack", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
            { channel: "webhook", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
            { channel: "push", enabled: false, posture: "DENIED", send_allowed: false, schedule_allowed: false },
          ],
          summary: { channel_count: 7, enabled_count: 0, send_allowed_count: 0, schedule_allowed_count: 0 },
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.lifecycle]: {
        ...base,
        lifecycle: { lifecycle_state: "NO_DATA", no_mutation_guarantee: true, visible_states: ["NO_DATA", "FAILED_CLOSED"] },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.delivery]: {
        ...base,
        delivery: { delivery_state: "NO_DATA", delivery_status: "NO_DATA", delivery_available: false, send_available: false, schedule_available: false, delivery_records: [], summary: { delivery_count: 0, sent_count: 0, scheduled_count: 0, failed_count: 0, blocked_count: 0 } },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.policy]: {
        ...base,
        policy: {
          global_governance_precedence: "highest",
          transmission_prohibition: "denied",
          schedule_prohibition: "denied",
          webhook_prohibition: "denied",
          broker_prohibition: "denied",
          mutation_prohibition: "denied",
          external_action_prohibition: "denied",
        },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.diagnostics]: {
        ...base,
        diagnostics: { diagnostic_state: "READY_WITH_LIMITATIONS", redaction_posture: "bounded", tenant_safe: true },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.compatibility]: {
        ...base,
        compatibility: { compatibility_state: "COMPATIBLE_WITH_LIMITATIONS", limitations: ["No outbound communication provider is implemented."] },
      },
      [CUSTOMER_COMMUNICATION_ENDPOINTS.apiContract]: {
        ...base,
        contract: {
          router: "customer-communication",
          phase: "PHASE65.6.6",
          canonical_pdf: { match_status: "MATCH", observed_page_count: 28 },
          routes: [
            { path: "/platform/customer-communication/health", method: "GET" },
            { path: "/platform/customer-communication/readiness", method: "GET" },
            { path: "/platform/customer-communication/identity", method: "GET" },
            { path: "/platform/customer-communication/registry", method: "GET" },
            { path: "/platform/customer-communication/catalogue", method: "GET" },
            { path: "/platform/customer-communication/templates", method: "GET" },
            { path: "/platform/customer-communication/preferences", method: "GET" },
            { path: "/platform/customer-communication/lifecycle", method: "GET" },
            { path: "/platform/customer-communication/delivery", method: "GET" },
            { path: "/platform/customer-communication/policy", method: "GET" },
            { path: "/platform/customer-communication/diagnostics", method: "GET" },
            { path: "/platform/customer-communication/compatibility", method: "GET" },
            { path: "/platform/customer-communication/api-contract", method: "GET" },
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
    const snapshot = await getCustomerCommunicationSnapshot();
    assert.equal(requests.length, 13);
    for (const request of requests) {
      assert.equal(request.options.method || "GET", "GET");
      assert.equal(request.options.credentials, "include");
      assert.ok(String(request.url).includes("/platform/customer-communication/"));
    }
    assert.equal(snapshot.status, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.readinessState, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.counts.notifications, 3);
    assert.equal(snapshot.counts.templates, 3);
    assert.equal(snapshot.counts.preferences, 7);
    assert.equal(snapshot.identity.workspace_id, "LMCP-COMM-65-6-6");
    assert.equal(snapshot.missionControlIntegration.workspace_lifecycle_state, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.apiContract.router, "customer-communication");
    assert.equal(snapshot.apiContract.canonical_pdf.match_status, "MATCH");
    assert.equal(snapshot.apiContract.routes.length, 13);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("customer communication workspace and Mission Control remain truthful", () => {
  assert.match(appSource, /Communication & Notifications/);
  assert.match(appSource, /CustomerCommunicationWorkspace/);
  assert.match(appSource, /getCustomerCommunicationSnapshot/);
  assert.match(appSource, /customer-communication/);
  assert.match(missionSource, /Phase65\.6\.6 Communication & Notifications/);
  assert.match(missionSource, /READY_FOR_PHASE65_6_7_SUPPORT_SERVICE_DESK/);
  assert.match(missionSource, /customer-communication/);
  assert.match(workspaceSource, /Communication & Notifications/);
  assert.match(workspaceSource, /No send buttons, compose forms, scheduling controls, or live message delivery interfaces are exposed\./);
  assert.match(workspaceSource, /No live messaging, email, SMS, WhatsApp, Teams, Slack, webhook, or push delivery is exposed\./);
  assert.match(apiSource, /Truthful read-only communication and notifications metadata/);
  assert.match(dashboardSource, /customer-communication/);
  assert.match(documentSource, /customer-communication/);
  assert.match(rfqSource, /customer-communication/);
  assert.match(apiSource, /CUSTOMER_COMMUNICATION_ENDPOINTS/);
  assert.match(apiSource, /getCustomerCommunicationSnapshot/);
  assert.match(apiSource, /credentials: "include"/);
  assert.match(apiSource, /\/platform\/customer-communication\/api-contract/);
});
