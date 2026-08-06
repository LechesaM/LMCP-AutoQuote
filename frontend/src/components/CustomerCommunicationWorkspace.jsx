import { ArrowLeftRight, Bell, BookOpenText, FileText, RefreshCw, ShieldCheck } from "lucide-react";

function toneForStatus(value) {
  const text = String(value || "").toUpperCase();
  if (text.includes("READY") || text.includes("COMPATIBLE") || text.includes("VALIDATED") || text.includes("IMPLEMENTED") || text.includes("REGISTERED_METADATA_ONLY")) return "good";
  if (text.includes("LIMITATION") || text.includes("NO_DATA") || text.includes("DATA_UNAVAILABLE") || text.includes("NOT_IMPLEMENTED") || text.includes("DRAFT_ONLY")) return "warning";
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

export default function CustomerCommunicationWorkspace({ view = {}, onNavigate = () => {} }) {
  const communication = view.customerCommunication || {};
  const identity = communication.identity || {};
  const registry = communication.registry || {};
  const catalogue = communication.catalogue || {};
  const templates = communication.templates || {};
  const preferences = communication.preferences || {};
  const delivery = communication.delivery || {};
  const lifecycle = communication.lifecycle || {};
  const policy = communication.policy || {};
  const diagnostics = communication.diagnostics || {};
  const compatibility = communication.compatibility || {};
  const health = communication.health || {};
  const readiness = communication.readiness || {};
  const missionControlIntegration = communication.missionControlIntegration || {};
  const registryItems = Array.isArray(registry.records) ? registry.records : [];
  const templateItems = Array.isArray(templates.templates) ? templates.templates : [];
  const preferenceItems = Array.isArray(preferences.channels) ? preferences.channels : [];
  const deliveryItems = Array.isArray(delivery.delivery_records) ? delivery.delivery_records : [];

  const readinessState = stateLabel(communication.readinessState || readiness.readiness_state || health.readiness_state);
  const lifecycleState = stateLabel(identity.lifecycle_state || lifecycle.lifecycle_state || "READY_WITH_LIMITATIONS");
  const healthState = stateLabel(communication.healthState || health.health_state || health.status || "READY_WITH_LIMITATIONS");
  const registryState = stateLabel(registry.registry_state || registry.catalogue_state || "REGISTERED_METADATA_ONLY");
  const templateState = stateLabel(templates.template_state || "REGISTERED_METADATA_ONLY");
  const deliveryState = stateLabel(delivery.delivery_state || delivery.delivery_status || "NO_DATA");

  return (
    <section className="card mission-panel customer-communication-workspace" aria-labelledby="customer-communication-heading">
      <SectionHeader
        eyebrow="Phase65.6.6"
        title="Communication & Notifications"
        description="Truthful read-only communication foundation. Messaging, sending, scheduling, webhooks, SMS, WhatsApp, Teams, Slack, push notifications, and autonomous delivery remain not implemented. No send buttons, compose forms, scheduling controls, or live message delivery interfaces are exposed. No live messaging, email, SMS, WhatsApp, Teams, Slack, webhook, or push delivery is exposed."
        action={<button type="button" className="mission-badge good" onClick={() => onNavigate("mission-control")}><RefreshCw size={14} /> Mission Control</button>}
      />

      <div className="mission-callouts">
        <span className={`mission-badge ${toneForStatus(readinessState)}`}>{readinessState}</span>
        <span className={`mission-badge ${toneForStatus(lifecycleState)}`}>{lifecycleState}</span>
        <span className={`mission-badge ${toneForStatus(healthState)}`}>{healthState}</span>
        <span className={`mission-badge ${toneForStatus(registryState)}`}>{registryState}</span>
      </div>

      <div className="mission-governance-grid">
        <StatusChip label="Notifications" value={countLabel(communication.counts?.notifications, registryItems.length)} source="/platform/customer-communication/registry" tone={toneForStatus(registryState)} />
        <StatusChip label="Templates" value={countLabel(communication.counts?.templates, templateItems.length)} source="/platform/customer-communication/templates" tone={toneForStatus(templateState)} />
        <StatusChip label="Preferences" value={countLabel(communication.counts?.preferences, preferenceItems.length)} source="/platform/customer-communication/preferences" tone="good" />
        <StatusChip label="Delivery" value={stateLabel(deliveryState, "NO_DATA")} source="/platform/customer-communication/delivery" tone={toneForStatus(deliveryState)} />
        <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
        <StatusChip label="Security" value="FAIL CLOSED" source="Communication policy" tone="good" />
      </div>

      <div className="mission-detail-grid">
        <DetailPanel label="Workspace identity" value={identity.canonical_name || "NO_DATA"} note={identity.workspace_id || "Workspace ID unavailable"} />
        <DetailPanel label="Portal reference" value={identity.portal_reference || "PHASE65_6_1_IMPLEMENTATION_COMPLETE"} note={identity.document_centre_reference || "Document centre reference unavailable"} />
        <DetailPanel label="Readiness" value={readinessState} note={(readiness.limitations || identity.accepted_limitations || []).join(" · ") || "Readiness remains truthful."} />
        <DetailPanel label="Compatibility" value={stateLabel(compatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS")} note={compatibility.limitations?.[0] || "Compatibility remains bounded"} />
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Notification registry</h3>
          <p className="muted">Notification records remain tenant-bound, metadata-only, and read only. No live communication is sent.</p>
          <div className="mission-work-list">
            {registryItems.slice(0, 6).map((item) => (
              <div key={item.notification_reference || item.reference || item.id} className="mission-work-row">
                <div>
                  <b>{item.notification_reference || item.reference || item.id || "NO_DATA"}</b>
                  <span>{item.lifecycle || "NO_DATA"} · {item.classification || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.communication_channel || "TENANT_CONTEXT_REQUIRED"}</b>
                  <span>{item.source_authority || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!registryItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Template catalogue</h3>
          <p className="muted">Templates remain metadata only and cannot render or send communication.</p>
          <div className="mission-work-list">
            {templateItems.slice(0, 6).map((item) => (
              <div key={item.template_reference || item.reference || item.id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.template_reference || item.id || "NO_DATA"}</b>
                  <span>{item.lifecycle || "NO_DATA"} · {item.classification || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.channel || "NO_DATA"}</b>
                  <span>{item.send_available ? "SENDABLE" : "DRAFT_ONLY"}</span>
                </div>
              </div>
            ))}
            {!templateItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Preferences and delivery posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Preferences" value={stateLabel(preferences.preference_state || "NO_DATA")} note={preferences.default_delivery_mode || "DRAFT_ONLY"} />
            <DetailPanel label="Delivery" value={deliveryState} note={delivery.delivery_available ? "Delivery metadata available" : "No outbound delivery is implemented."} />
            <DetailPanel label="Lifecycle" value={stateLabel(lifecycle.lifecycle_state || "NO_DATA")} note={lifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            <DetailPanel label="Policy" value={policy.global_governance_precedence || "highest"} note={policy.transmission_prohibition || "denied"} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Operational constraints</h3>
          <p className="muted">The workspace is read only. No send, compose, schedule, webhook, queue, broker, or live messaging controls are implemented.</p>
          <ul className="mission-bullet-list">
            <li>Communication metadata is not fabricated.</li>
            <li>Visibility remains tenant bound.</li>
            <li>Outbound delivery is disabled.</li>
            <li>Governance and security remain fail closed.</li>
          </ul>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Source posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Catalogue" value={stateLabel(catalogue.catalogue_state || "NO_DATA")} note={catalogue.title || "Notification Catalogue"} />
            <DetailPanel label="Templates" value={stateLabel(templates.template_state || "NO_DATA")} note={templates.title || "Template Catalogue"} />
            <DetailPanel label="Diagnostics" value={diagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={diagnostics.limitations?.[0] || "Diagnostics are redacted."} />
            <DetailPanel label="Mission Control" value={missionControlIntegration.workspace_lifecycle_state || "READY_WITH_LIMITATIONS"} note={missionControlIntegration.current_milestone || "PHASE65.6.6_COMMUNICATION_AND_NOTIFICATIONS"} />
            <DetailPanel label="Next authorised milestone" value={missionControlIntegration.next_authorized_milestone || "PHASE65.6.7_SUPPORT_SERVICE_DESK"} note="Later feature remains deferred." />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Delivery and preference records</h3>
          <div className="mission-work-list">
            {preferenceItems.slice(0, 6).map((item) => (
              <div key={item.channel} className="mission-work-row">
                <div>
                  <b>{item.channel || "NO_DATA"}</b>
                  <span>{item.posture || "DENIED"} · {item.delivery_mode || "DRAFT_ONLY"}</span>
                </div>
                <div>
                  <b>{item.enabled ? "ENABLED" : "DISABLED"}</b>
                  <span>{item.schedule_allowed ? "SCHEDULED" : "NO SCHEDULE"}</span>
                </div>
              </div>
            ))}
            {!preferenceItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Delivery records" value={countLabel(deliveryItems.length, "0")} note="No outbound delivery events exist." />
            <DetailPanel label="Registry records" value={countLabel(registryItems.length, "0")} note="Truthful notification registry" />
            <DetailPanel label="Template records" value={countLabel(templateItems.length, "0")} note="Truthful template catalogue" />
            <DetailPanel label="Preferences" value={countLabel(preferenceItems.length, "0")} note="Truthful channel posture" />
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Navigation</h3>
          <div className="mission-action-grid">
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-dashboard")}><BookOpenText size={15} /> Open Customer Dashboard</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-document-centre")}><FileText size={15} /> Open Secure Document Centre</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-rfq-quotes")}><Bell size={15} /> Open RFQ & Quote Workspace</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-self-service-portal")}><ShieldCheck size={15} /> Open Customer Portal</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("mission-control")}><ArrowLeftRight size={15} /> Return to Mission Control</button>
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Limitations</h3>
          <p className="muted">No send buttons, compose forms, scheduling controls, or live message delivery interfaces are exposed.</p>
          <ul className="mission-bullet-list">
            {(identity.accepted_limitations || []).slice(0, 4).map((item) => (
              <li key={item}>{item}</li>
            ))}
            {!identity.accepted_limitations?.length ? <li>No limitations recorded.</li> : null}
          </ul>
        </div>
      </div>
    </section>
  );
}
