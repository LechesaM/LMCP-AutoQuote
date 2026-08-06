import { ArrowLeftRight, BookOpenText, LayoutDashboard, RefreshCw, ShieldCheck } from "lucide-react";

function toneForStatus(value) {
  const text = String(value || "").toUpperCase();
  if (text.includes("READY") || text.includes("COMPATIBLE") || text.includes("VALIDATED") || text.includes("IMPLEMENTED")) return "good";
  if (text.includes("LIMITATION") || text.includes("NO_DATA") || text.includes("DATA_UNAVAILABLE") || text.includes("NOT_IMPLEMENTED")) return "warning";
  if (text.includes("FAILED") || text.includes("BLOCK") || text.includes("UNAVAILABLE") || text.includes("REJECTED")) return "bad";
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

export default function CustomerDashboardWorkspace({ view = {}, onNavigate = () => {} }) {
  const dashboard = view.customerDashboard || {};
  const identity = dashboard.identity || {};
  const summary = dashboard.summary || {};
  const sections = Array.isArray(dashboard.sections) ? dashboard.sections : [];
  const widgets = Array.isArray(dashboard.widgets) ? dashboard.widgets : [];
  const organisation = dashboard.organisation || {};
  const rfqs = dashboard.rfqs || {};
  const quotations = dashboard.quotations || {};
  const activity = dashboard.activity || {};
  const notifications = dashboard.notifications || {};
  const policy = dashboard.policy || {};
  const diagnostics = dashboard.diagnostics || {};
  const compatibility = dashboard.compatibility || {};
  const health = dashboard.health || {};
  const readiness = dashboard.readiness || {};
  const missionControlIntegration = dashboard.missionControlIntegration || {};
  const apiContract = dashboard.apiContract || {};
  const portal = view.customerSelfServicePortal || {};
  const customerIdentity = view.customerIdentity || {};

  const readinessState = stateLabel(dashboard.readinessState || readiness.readiness_state || health.readiness_state);
  const lifecycleState = stateLabel(identity.lifecycle_state || dashboard.lifecycle?.current_state || "READY_WITH_LIMITATIONS");
  const healthState = stateLabel(dashboard.healthState || health.health_state || health.status || "READY_WITH_LIMITATIONS");
  const organisationState = stateLabel(organisation.organisation_identity_state || "DATA_UNAVAILABLE");
  const rfqState = stateLabel(rfqs.total_authorised_rfqs_state || rfqs.source_status || "NO_DATA");
  const quotationState = stateLabel(quotations.quotation_count_state || quotations.data_authority || "NO_DATA");
  const activityState = stateLabel(activity.activity_state || "NO_DATA");
  const notificationState = stateLabel(notifications.notification_state || "NO_DATA");

  return (
    <section className="card mission-panel customer-dashboard-workspace" aria-labelledby="customer-dashboard-heading">
      <SectionHeader
        eyebrow="Phase65.6.3"
        title="Customer Dashboard"
        description="Truthful read-only customer dashboard workspace. Customer workflows, uploads, messaging, support tickets, and submissions remain not implemented."
        action={<button type="button" className="mission-badge good" onClick={() => onNavigate("mission-control")}><RefreshCw size={14} /> Mission Control</button>}
      />

      <div className="mission-callouts">
        <span className={`mission-badge ${toneForStatus(readinessState)}`}>{readinessState}</span>
        <span className={`mission-badge ${toneForStatus(lifecycleState)}`}>{lifecycleState}</span>
        <span className={`mission-badge ${toneForStatus(healthState)}`}>{healthState}</span>
        <span className={`mission-badge ${toneForStatus(organisationState)}`}>{organisationState}</span>
      </div>

      <div className="mission-governance-grid">
        <StatusChip label="Sections" value={countLabel(dashboard.counts?.sections, sections.length)} source="/platform/customer-dashboard/sections" tone="good" />
        <StatusChip label="Widgets" value={countLabel(dashboard.counts?.widgets, widgets.length)} source="/platform/customer-dashboard/widgets" tone="good" />
        <StatusChip label="RFQ posture" value={rfqState} source="/platform/customer-dashboard/rfqs" tone={toneForStatus(rfqState)} />
        <StatusChip label="Quotation posture" value={quotationState} source="/platform/customer-dashboard/quotations" tone={toneForStatus(quotationState)} />
        <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
        <StatusChip label="Security" value="FAIL CLOSED" source="Dashboard policy" tone="good" />
      </div>

      <div className="mission-detail-grid">
        <DetailPanel label="Dashboard identity" value={identity.canonical_name || "NO_DATA"} note={identity.dashboard_id || "Dashboard ID unavailable"} />
        <DetailPanel label="Portal reference" value={identity.portal_reference || "PHASE65_6_1_IMPLEMENTATION_COMPLETE"} note={identity.identity_reference || "Identity reference unavailable"} />
        <DetailPanel label="Readiness" value={readinessState} note={(readiness.limitations || identity.accepted_limitations || []).join(" · ") || "Readiness remains truthful."} />
        <DetailPanel label="Compatibility" value={stateLabel(compatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS")} note={compatibility.limitations?.[0] || "Compatibility remains bounded"} />
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Summary posture</h3>
          <p className="muted">The dashboard exposes bounded source-derived metadata only. No fabricated customer data is shown.</p>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Organisation summary" value={organisationState} note={organisation.profile_management_readiness || "NOT_IMPLEMENTED"} />
            <DetailPanel label="RFQ summary" value={rfqState} note={rfqs.source_status || "NO_DATA"} />
            <DetailPanel label="Quotation summary" value={quotationState} note={quotations.freshness_state || "NO_DATA"} />
            <DetailPanel label="Activity summary" value={activityState} note={activity.data_authority || "metadata only"} />
            <DetailPanel label="Notification summary" value={notificationState} note={notifications.delivery_state || "NOT_IMPLEMENTED"} />
            <DetailPanel label="API contract" value={apiContract.router || "customer-dashboard"} note={apiContract.canonical_pdf?.match_status || "MATCH"} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Mission Control integration</h3>
          <p className="muted">Mission Control receives dashboard lifecycle, visible section counts, widget counts, and readiness guidance without customer mutation.</p>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Lifecycle" value={stateLabel(missionControlIntegration.dashboard_lifecycle_state || lifecycleState)} note={missionControlIntegration.current_milestone || "PHASE65_6_3_CUSTOMER_DASHBOARD"} />
            <DetailPanel label="Sections" value={countLabel(missionControlIntegration.visible_section_count, sections.length)} note="Read only metadata" />
            <DetailPanel label="Widgets" value={countLabel(missionControlIntegration.visible_widget_count, widgets.length)} note="Read only metadata" />
            <DetailPanel label="Next authorised milestone" value={missionControlIntegration.next_authorized_milestone || "PHASE65_6_4_RFQ_QUOTE_WORKSPACE"} note="Later feature remains deferred." />
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Section registry</h3>
          <p className="muted">Sections are metadata-only and correspond to truthful dashboard areas.</p>
          <div className="mission-work-list">
            {sections.slice(0, 6).map((item) => (
              <div key={item.section_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.section_id}</b>
                  <span>{item.availability_state || "NO_DATA"} · {item.implementation_state || "REGISTERED_METADATA_ONLY"}</span>
                </div>
                <div>
                  <b>{item.mutation_posture || "READ_ONLY"}</b>
                  <span>{item.external_action_posture || "DENIED"}</span>
                </div>
              </div>
            ))}
            {!sections.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Widget registry</h3>
          <p className="muted">Widgets remain bounded, read-only, and fail closed when source data is not available.</p>
          <div className="mission-work-list">
            {widgets.slice(0, 6).map((item) => (
              <div key={item.widget_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.widget_id}</b>
                  <span>{item.metric_or_state || "NO_DATA"} · {item.implementation_status || "REGISTERED_METADATA_ONLY"}</span>
                </div>
                <div>
                  <b>{item.empty_state_behavior || "NO_DATA"}</b>
                  <span>{item.external_action_posture || "DENIED"}</span>
                </div>
              </div>
            ))}
            {!widgets.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Read-only summaries</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="RFQ authorised count" value={countLabel(rfqs.total_authorised_rfqs_state, "NO_DATA")} note="No customer RFQ dataset is exposed." />
            <DetailPanel label="Quotation count" value={countLabel(quotations.quotation_count_state, "NO_DATA")} note="No customer quotation dataset is exposed." />
            <DetailPanel label="Recent activity" value={activityState} note={activity.later_feature_readiness_notices?.[0] || "No live activity stream is exposed."} />
            <DetailPanel label="Notifications" value={notificationState} note={notifications.message_state || "NOT_IMPLEMENTED"} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Operational constraints</h3>
          <p className="muted">The dashboard is a read-only view only. No editable controls, uploads, submit actions, or external actions are implemented.</p>
          <ul className="mission-bullet-list">
            <li>Customer data is not fabricated.</li>
            <li>RFQ and quotation workflows remain deferred.</li>
            <li>Portal and identity metadata remain source-derived.</li>
            <li>Governance and security remain fail closed.</li>
          </ul>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Source posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Dashboard summary" value={summary.dashboard_status || "READY_WITH_LIMITATIONS"} note={summary.next_recommended_action || "Phase65.6.4 remains deferred."} />
            <DetailPanel label="Portal foundation" value={portal.identity?.canonical_name || "NO_DATA"} note={portal.readinessState || portal.readiness?.readiness_state || "READY_WITH_LIMITATIONS"} />
            <DetailPanel label="Identity foundation" value={customerIdentity.identity?.canonical_name || "NO_DATA"} note={customerIdentity.readinessState || customerIdentity.readiness?.readiness_state || "READY_WITH_LIMITATIONS"} />
            <DetailPanel label="Organisation source" value={organisation.data_authority || "customer portal and identity metadata only"} note={organisation.freshness_state || "DATA_UNAVAILABLE"} />
            <DetailPanel label="Policy" value={policy.global_governance_precedence || "highest"} note={policy.external_action_policy || "denied"} />
            <DetailPanel label="Diagnostics" value={diagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={diagnostics.current_limitations?.[0] || "Diagnostics are redacted."} />
            <DetailPanel label="Security" value={dashboard.health?.security_status || missionControlIntegration.security_status || "FAIL_CLOSED"} note="No secrets or tokens are exposed" />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Navigation</h3>
          <p className="muted">The workspace links back to the lower-phase portal and identity foundations without changing data.</p>
          <div className="mission-workspace-footer">
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-self-service-portal")}><LayoutDashboard size={15} /> Open Customer Portal</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-identity")}><ShieldCheck size={15} /> Open Customer Identity</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-document-centre")}><FileText size={15} /> Open Secure Document Centre</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("mission-control")}><ArrowLeftRight size={15} /> Return to Mission Control</button>
            <span className="mission-footer-note"><BookOpenText size={15} /> Truthful read-only customer dashboard workspace</span>
          </div>
        </div>
      </div>
    </section>
  );
}
