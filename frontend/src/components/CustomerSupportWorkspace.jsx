import { ArrowLeftRight, BookOpenText, ClipboardList, RefreshCw, ShieldCheck } from "lucide-react";

function toneForStatus(value) {
  const text = String(value || "").toUpperCase();
  if (text.includes("READY") || text.includes("COMPATIBLE") || text.includes("VALIDATED") || text.includes("IMPLEMENTED") || text.includes("REGISTERED_METADATA_ONLY")) return "good";
  if (text.includes("LIMITATION") || text.includes("NO_DATA") || text.includes("DATA_UNAVAILABLE") || text.includes("NOT_IMPLEMENTED")) return "warning";
  if (text.includes("FAILED") || text.includes("BLOCK") || text.includes("UNAVAILABLE") || text.includes("REJECTED") || text.includes("DENIED")) return "bad";
  if (text.includes("DISABLED") || text.includes("DEFINED_NOT_IMPLEMENTED")) return "neutral";
  return "neutral";
}

function SectionHeader({ eyebrow, title, description, action = null }) {
  return (
    <div className="mission-section-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      {action}
    </div>
  );
}

function StatusChip({ label, value, source, tone = "neutral" }) {
  return (
    <div className={`mission-status-chip ${tone}`}>
      <span>{label}</span>
      <b>{value}</b>
      <small>{source}</small>
    </div>
  );
}

function DetailPanel({ label, value, note }) {
  return (
    <div className="mission-detail-panel">
      <span>{label}</span>
      <b>{value}</b>
      <small>{note}</small>
    </div>
  );
}

function countLabel(value, fallback = "NO_DATA") {
  if (value === null || value === undefined || value === "") return fallback;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value);
  return String(amount);
}

function stateLabel(value, fallback = "NO_DATA") {
  const text = String(value || fallback).trim();
  return text ? text.toUpperCase() : fallback;
}

export default function CustomerSupportWorkspace({ view = {}, onNavigate = () => {} }) {
  const support = view.customerSupport || {};
  const identity = support.identity || {};
  const cases = support.cases || {};
  const priorities = support.priorities || {};
  const slas = support.slas || {};
  const queues = support.queues || {};
  const knowledgeBase = support.knowledgeBase || {};
  const lifecycle = support.lifecycle || {};
  const policy = support.policy || {};
  const diagnostics = support.diagnostics || {};
  const compatibility = support.compatibility || {};
  const health = support.health || {};
  const readiness = support.readiness || {};
  const missionControlIntegration = support.missionControlIntegration || {};

  const caseItems = Array.isArray(cases.records) ? cases.records : [];
  const priorityItems = Array.isArray(priorities.priorities) ? priorities.priorities : [];
  const slaItems = Array.isArray(slas.slas) ? slas.slas : [];
  const queueItems = Array.isArray(queues.queues) ? queues.queues : [];
  const knowledgeItems = Array.isArray(knowledgeBase.records) ? knowledgeBase.records : [];
  const supportPreferences = Array.isArray(policy.support_preferences) ? policy.support_preferences : [];

  const readinessState = stateLabel(support.readinessState || readiness.readiness_state || health.readiness_state);
  const lifecycleState = stateLabel(identity.lifecycle_state || lifecycle.lifecycle_state || "READY_WITH_LIMITATIONS");
  const healthState = stateLabel(support.healthState || health.health_state || health.status || "READY_WITH_LIMITATIONS");
  const caseState = stateLabel(cases.registry_state || cases.catalogue_state || "REGISTERED_METADATA_ONLY");
  const priorityState = stateLabel(priorities.priority_state || "REGISTERED_METADATA_ONLY");
  const slaState = stateLabel(slas.sla_state || "REGISTERED_METADATA_ONLY");
  const queueState = stateLabel(queues.queue_state || "REGISTERED_METADATA_ONLY");
  const knowledgeState = stateLabel(knowledgeBase.knowledge_state || "REGISTERED_METADATA_ONLY");

  return (
    <section className="card mission-panel customer-support-workspace" aria-labelledby="customer-support-heading">
      <SectionHeader
        eyebrow="Phase65.6.7"
        title="Support & Service Desk"
        description="Truthful read-only support foundation. Ticket creation, editing, closure, assignment, escalation, live SLA monitoring, chat, and external ITSM integrations remain not implemented."
        action={<button type="button" className="mission-badge good" onClick={() => onNavigate("mission-control")}><RefreshCw size={14} /> Mission Control</button>}
      />

      <div className="mission-callouts">
        <span className={`mission-badge ${toneForStatus(readinessState)}`}>{readinessState}</span>
        <span className={`mission-badge ${toneForStatus(lifecycleState)}`}>{lifecycleState}</span>
        <span className={`mission-badge ${toneForStatus(healthState)}`}>{healthState}</span>
        <span className={`mission-badge ${toneForStatus(caseState)}`}>{caseState}</span>
      </div>

      <div className="mission-governance-grid">
        <StatusChip label="Cases" value={countLabel(support.counts?.cases, caseItems.length)} source="/platform/customer-support/cases" tone={toneForStatus(caseState)} />
        <StatusChip label="Priorities" value={countLabel(support.counts?.priorities, priorityItems.length)} source="/platform/customer-support/priorities" tone={toneForStatus(priorityState)} />
        <StatusChip label="SLAs" value={countLabel(support.counts?.slas, slaItems.length)} source="/platform/customer-support/slas" tone={toneForStatus(slaState)} />
        <StatusChip label="Queues" value={countLabel(support.counts?.queues, queueItems.length)} source="/platform/customer-support/queues" tone={toneForStatus(queueState)} />
        <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
        <StatusChip label="Security" value="FAIL CLOSED" source="Support policy" tone="good" />
      </div>

      <div className="mission-detail-grid">
        <DetailPanel label="Workspace identity" value={identity.canonical_name || "NO_DATA"} note={identity.workspace_id || "Workspace ID unavailable"} />
        <DetailPanel label="Portal reference" value={identity.portal_reference || "PHASE65_6_1_IMPLEMENTATION_COMPLETE"} note={identity.communication_reference || "Communication reference unavailable"} />
        <DetailPanel label="Readiness" value={readinessState} note={(readiness.limitations || identity.accepted_limitations || []).join(" · ") || "Readiness remains truthful."} />
        <DetailPanel label="Compatibility" value={stateLabel(compatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS")} note={compatibility.limitations?.[0] || "Compatibility remains bounded"} />
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Support case registry</h3>
          <p className="muted">Support cases are metadata only and remain tenant bound. No live ticket creation or modification is exposed.</p>
          <div className="mission-work-list">
            {caseItems.slice(0, 6).map((item) => (
              <div key={item.case_reference || item.ticket_reference} className="mission-work-row">
                <div>
                  <b>{item.case_reference || item.ticket_reference || "NO_DATA"}</b>
                  <span>{item.priority || "NO_DATA"} · {item.classification || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.queue || "TENANT_CONTEXT_REQUIRED"}</b>
                  <span>{item.source_authority || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!caseItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Priority, SLA, queue and knowledge metadata</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Priorities" value={priorityState} note={priorityItems[0]?.sla_reference || "Priority metadata only"} />
            <DetailPanel label="SLAs" value={slaState} note={slaItems[0]?.response_window || "SLA metadata only"} />
            <DetailPanel label="Queues" value={queueState} note={queueItems[0]?.support_scope || "Queue metadata only"} />
            <DetailPanel label="Knowledge base" value={knowledgeState} note={knowledgeItems[0]?.article_title || "Knowledge metadata only"} />
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Assignment and preferences</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Assignments" value={countLabel(support.counts?.assignments, 3)} note="Assignment metadata only. No agent handoff is exposed." />
            <DetailPanel label="Support preferences" value={countLabel(supportPreferences.length, 7)} note={supportPreferences[0]?.posture || "DRAFT_ONLY"} />
            <DetailPanel label="Lifecycle" value={stateLabel(lifecycle.lifecycle_state || "NO_DATA")} note={lifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            <DetailPanel label="Diagnostics" value={diagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={diagnostics.limitations?.[0] || "Diagnostics are redacted."} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Operational constraints</h3>
          <p className="muted">The workspace is read only. No create ticket, reply, close, upload, or chat controls are implemented.</p>
          <ul className="mission-bullet-list">
            <li>Support metadata is not fabricated.</li>
            <li>Visibility remains tenant bound.</li>
            <li>Escalation and SLA execution are disabled.</li>
            <li>Governance and security remain fail closed.</li>
          </ul>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Source posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Cases" value={caseState} note={cases.title || "Support Case Catalogue"} />
            <DetailPanel label="Priorities" value={priorityState} note={priorities.title || "Priority Catalogue"} />
            <DetailPanel label="SLAs" value={slaState} note={slas.title || "SLA Metadata"} />
            <DetailPanel label="Queues" value={queueState} note={queues.title || "Queue Registry"} />
            <DetailPanel label="Knowledge base" value={knowledgeState} note={knowledgeBase.title || "Knowledge Base Catalogue"} />
            <DetailPanel label="Policy" value={policy.global_governance_precedence || "highest"} note={policy.ticket_creation_prohibition || "denied"} />
            <DetailPanel label="Mission Control" value={missionControlIntegration.workspace_lifecycle_state || "READY_WITH_LIMITATIONS"} note={missionControlIntegration.current_milestone || "PHASE65.6.7_SUPPORT_AND_SERVICE_DESK"} />
            <DetailPanel label="Next authorised milestone" value={missionControlIntegration.next_authorized_milestone || "PHASE65.6.8_CUSTOMER_PROFILE_TENANT_MANAGEMENT"} note="Later feature remains deferred." />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Navigation</h3>
          <div className="mission-action-grid">
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-dashboard")}><BookOpenText size={15} /> Open Customer Dashboard</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-communication")}><ClipboardList size={15} /> Open Communication & Notifications</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-self-service-portal")}><ShieldCheck size={15} /> Open Customer Portal</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("mission-control")}><ArrowLeftRight size={15} /> Return to Mission Control</button>
          </div>
        </div>
      </div>
    </section>
  );
}
