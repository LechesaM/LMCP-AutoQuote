import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  CUSTOMER_SUPPORT_ENDPOINTS,
  getCustomerSupportSnapshot,
} from "../src/services/customerSupportApi.js";

const appSource = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const missionSource = readFileSync(new URL("../src/components/MissionControlLanding.jsx", import.meta.url), "utf8");
const dashboardSource = readFileSync(new URL("../src/components/CustomerDashboardWorkspace.jsx", import.meta.url), "utf8");
const communicationSource = readFileSync(new URL("../src/components/CustomerCommunicationWorkspace.jsx", import.meta.url), "utf8");
const workspaceSource = readFileSync(new URL("../src/components/CustomerSupportWorkspace.jsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/services/customerSupportApi.js", import.meta.url), "utf8");

test("customer support snapshot is read only and namespaced", async () => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), options });
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const basePath = path.split("?")[0];
    const base = {
      status: "READY_WITH_LIMITATIONS",
      scope: "customer_support",
      data_state: "READY_WITH_LIMITATIONS",
    };

    const payloads = {
      [CUSTOMER_SUPPORT_ENDPOINTS.health]: {
        ...base,
        health_state: "READY_WITH_LIMITATIONS",
        readiness_state: "READY_WITH_LIMITATIONS",
        mission_control_integration: {
          workspace_lifecycle_state: "READY_WITH_LIMITATIONS",
          governance_status: "PRESERVED",
          security_status: "FAIL_CLOSED",
          visible_case_count: 3,
          visible_priority_count: 4,
          visible_sla_count: 3,
          visible_queue_count: 3,
          visible_knowledge_count: 3,
          visible_assignment_count: 3,
          visible_support_preference_count: 7,
          current_milestone: "PHASE65.6.7_SUPPORT_AND_SERVICE_DESK",
          next_authorized_milestone: "PHASE65.6.8_CUSTOMER_PROFILE_TENANT_MANAGEMENT",
        },
        frontend_experience: {
          workspace: "CustomerSupportWorkspace",
          truthfulness: "Truthful read-only support metadata with no fabricated support activity.",
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.readiness]: { ...base, readiness_state: "READY_WITH_LIMITATIONS", limitations: ["Support foundation remains read only."] },
      [CUSTOMER_SUPPORT_ENDPOINTS.identity]: {
        ...base,
        identity: {
          workspace_id: "LMCP-SUPP-65-6-7",
          canonical_name: "LMCP AutoQuote Support & Service Desk",
          portal_reference: "PHASE65_6_1_IMPLEMENTATION_COMPLETE",
          identity_reference: "PHASE65_6_2_IMPLEMENTATION_COMPLETE",
          dashboard_reference: "PHASE65_6_3_IMPLEMENTATION_COMPLETE",
          communication_reference: "PHASE65_6_6_IMPLEMENTATION_COMPLETE",
          lifecycle_state: "READY_WITH_LIMITATIONS",
          mutation_posture: "READ_ONLY",
          external_action_posture: "DENIED",
          accepted_limitations: ["No live support ticketing is implemented."],
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.cases]: {
        ...base,
        cases: {
          registry_state: "REGISTERED_METADATA_ONLY",
          records: [
            { case_reference: "support-readiness-case", priority: "normal", classification: "GOVERNANCE_NOTICE", queue: "metadata-review", source_authority: "Support centre metadata only" },
            { case_reference: "support-queue-review-case", priority: "high", classification: "QUEUE_NOTICE", queue: "triage-review", source_authority: "Support centre metadata only" },
            { case_reference: "support-knowledge-case", priority: "normal", classification: "KNOWLEDGE_NOTICE", queue: "knowledge-base", source_authority: "Support centre metadata only" },
          ],
          summary: { record_count: 3 },
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.priorities]: {
        ...base,
        priorities: {
          priority_state: "REGISTERED_METADATA_ONLY",
          priorities: [
            { priority: "low", severity: "low", sla_reference: "sla-standard" },
            { priority: "normal", severity: "medium", sla_reference: "sla-standard" },
            { priority: "high", severity: "high", sla_reference: "sla-priority" },
            { priority: "urgent", severity: "critical", sla_reference: "sla-critical" },
          ],
          summary: { priority_count: 4 },
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.slas]: {
        ...base,
        slas: {
          sla_state: "REGISTERED_METADATA_ONLY",
          slas: [
            { sla_reference: "sla-standard", response_window: "4 business hours", resolution_window: "2 business days" },
            { sla_reference: "sla-priority", response_window: "2 business hours", resolution_window: "1 business day" },
            { sla_reference: "sla-critical", response_window: "30 minutes", resolution_window: "same day" },
          ],
          summary: { sla_count: 3 },
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.queues]: {
        ...base,
        queues: {
          queue_state: "REGISTERED_METADATA_ONLY",
          queues: [
            { queue_reference: "metadata-review", support_scope: "metadata review" },
            { queue_reference: "triage-review", support_scope: "triage review" },
            { queue_reference: "knowledge-base", support_scope: "knowledge base" },
          ],
          summary: { queue_count: 3 },
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.knowledgeBase]: {
        ...base,
        knowledge_base: {
          knowledge_state: "REGISTERED_METADATA_ONLY",
          records: [
            { knowledge_reference: "kb-support-readiness", article_title: "Support Readiness" },
            { knowledge_reference: "kb-queue-routing", article_title: "Queue Routing" },
            { knowledge_reference: "kb-knowledge-base", article_title: "Knowledge Base" },
          ],
          summary: { article_count: 3 },
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.lifecycle]: {
        ...base,
        lifecycle: { lifecycle_state: "NO_DATA", no_mutation_guarantee: true },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.policy]: {
        ...base,
        policy: {
          global_governance_precedence: "highest",
          ticket_creation_prohibition: "denied",
          escalation_prohibition: "denied",
          webhook_prohibition: "denied",
          email_prohibition: "denied",
          support_preferences: [
            { channel: "email", posture: "DRAFT_ONLY" },
            { channel: "sms", posture: "DENIED" },
            { channel: "teams", posture: "DENIED" },
            { channel: "slack", posture: "DENIED" },
            { channel: "whatsapp", posture: "DENIED" },
            { channel: "chatbot", posture: "DENIED" },
            { channel: "live_chat", posture: "DENIED" },
          ],
        },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.diagnostics]: {
        ...base,
        diagnostics: { diagnostic_state: "READY_WITH_LIMITATIONS", current_limitations: ["Diagnostics are redacted and bounded."] },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.compatibility]: {
        ...base,
        compatibility: { compatibility_state: "COMPATIBLE_WITH_LIMITATIONS", limitations: ["No live support activity is implemented."] },
      },
      [CUSTOMER_SUPPORT_ENDPOINTS.apiContract]: {
        ...base,
        contract: {
          router: "customer-support",
          phase: "PHASE65.6.7",
          canonical_pdf: { match_status: "MATCH", observed_page_count: 28 },
          routes: [
            { path: "/platform/customer-support/health", method: "GET" },
            { path: "/platform/customer-support/readiness", method: "GET" },
            { path: "/platform/customer-support/identity", method: "GET" },
            { path: "/platform/customer-support/cases", method: "GET" },
            { path: "/platform/customer-support/priorities", method: "GET" },
            { path: "/platform/customer-support/slas", method: "GET" },
            { path: "/platform/customer-support/queues", method: "GET" },
            { path: "/platform/customer-support/knowledge-base", method: "GET" },
            { path: "/platform/customer-support/lifecycle", method: "GET" },
            { path: "/platform/customer-support/policy", method: "GET" },
            { path: "/platform/customer-support/diagnostics", method: "GET" },
            { path: "/platform/customer-support/compatibility", method: "GET" },
            { path: "/platform/customer-support/api-contract", method: "GET" },
          ],
        },
      },
    };

    return {
      ok: true,
      json: async () => payloads[basePath] || base,
    };
  };

  try {
    const snapshot = await getCustomerSupportSnapshot();
    assert.equal(requests.length, 13);
    for (const request of requests) {
      assert.equal(request.options.method || "GET", "GET");
      assert.equal(request.options.credentials, "include");
      assert.ok(String(request.url).includes("/platform/customer-support/"));
    }
    assert.equal(snapshot.status, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.readinessState, "READY_WITH_LIMITATIONS");
    assert.equal(snapshot.counts.cases, 3);
    assert.equal(snapshot.counts.priorities, 4);
    assert.equal(snapshot.counts.slas, 3);
    assert.equal(snapshot.counts.queues, 3);
    assert.equal(snapshot.counts.knowledge, 3);
    assert.equal(snapshot.counts.preferences, 7);
    assert.equal(snapshot.identity.workspace_id, "LMCP-SUPP-65-6-7");
    assert.equal(snapshot.apiContract.router, "customer-support");
    assert.equal(snapshot.apiContract.canonical_pdf.match_status, "MATCH");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("customer support workspace and Mission Control remain truthful", () => {
  assert.match(appSource, /Support & Service Desk/);
  assert.match(appSource, /CustomerSupportWorkspace/);
  assert.match(appSource, /getCustomerSupportSnapshot/);
  assert.match(appSource, /customer-support/);
  assert.match(missionSource, /Phase65\.6\.7 Support & Service Desk/);
  assert.match(missionSource, /READY_FOR_PHASE65_6_8_CUSTOMER_PROFILE_TENANT_MANAGEMENT/);
  assert.match(missionSource, /Read-only support metadata only/);
  assert.match(dashboardSource, /Open Support & Service Desk/);
  assert.match(communicationSource, /Open Support & Service Desk/);
  assert.match(workspaceSource, /Support & Service Desk/);
  assert.match(workspaceSource, /Truthful read-only support foundation\./);
  assert.match(workspaceSource, /Ticket creation, editing, closure, assignment, escalation, live SLA monitoring, chat, and external ITSM integrations remain not implemented\./);
  assert.match(apiSource, /CUSTOMER_SUPPORT_ENDPOINTS/);
  assert.match(apiSource, /getCustomerSupportSnapshot/);
  assert.match(apiSource, /credentials: "include"/);
  assert.match(apiSource, /\/platform\/customer-support\/api-contract/);
});
