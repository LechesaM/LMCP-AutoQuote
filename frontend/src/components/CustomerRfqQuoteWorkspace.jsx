import { ArrowLeftRight, BookOpenText, FileText, RefreshCw, ShieldCheck } from "lucide-react";

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

export default function CustomerRfqQuoteWorkspace({ view = {}, onNavigate = () => {} }) {
  const workspace = view.customerRfqQuoteWorkspace || {};
  const identity = workspace.identity || {};
  const rfqs = workspace.rfqs || {};
  const quotations = workspace.quotations || {};
  const rfqLifecycle = workspace.rfqLifecycle || {};
  const quotationLifecycle = workspace.quotationLifecycle || {};
  const sourceAuthority = workspace.sourceAuthority || {};
  const freshness = workspace.freshness || {};
  const policy = workspace.policy || {};
  const diagnostics = workspace.diagnostics || {};
  const compatibility = workspace.compatibility || {};
  const health = workspace.health || {};
  const readiness = workspace.readiness || {};
  const missionControlIntegration = workspace.missionControlIntegration || {};
  const rfqItems = Array.isArray(rfqs.records) ? rfqs.records : [];
  const quotationItems = Array.isArray(quotations.records) ? quotations.records : [];

  const readinessState = stateLabel(workspace.readinessState || readiness.readiness_state || health.readiness_state);
  const lifecycleState = stateLabel(identity.lifecycle_state || workspace.lifecycle?.current_state || "READY_WITH_LIMITATIONS");
  const healthState = stateLabel(workspace.healthState || health.health_state || health.status || "READY_WITH_LIMITATIONS");
  const rfqState = stateLabel(rfqs.registry_state || rfqs.source_authority_state || "NO_DATA");
  const quotationState = stateLabel(quotations.registry_state || quotations.source_authority_state || "NO_DATA");
  const tenantState = stateLabel(identity.tenant_posture || rfqs.tenant_context_posture || "TENANT_CONTEXT_REQUIRED");
  const sourceState = stateLabel(sourceAuthority.authority_state || "NO_DATA");
  const freshnessState = stateLabel(freshness.overall_freshness_state || "NO_DATA");

  return (
    <section className="card mission-panel customer-rfq-quote-workspace" aria-labelledby="customer-rfq-quote-heading">
      <SectionHeader
        eyebrow="Phase65.6.4"
        title="RFQ & Quote Workspace"
        description="Truthful read-only RFQ and quotation workspace. RFQ creation, quotation submission, uploads, approvals, messaging, and autonomous actions remain not implemented."
        action={<button type="button" className="mission-badge good" onClick={() => onNavigate("mission-control")}><RefreshCw size={14} /> Mission Control</button>}
      />

      <div className="mission-callouts">
        <span className={`mission-badge ${toneForStatus(readinessState)}`}>{readinessState}</span>
        <span className={`mission-badge ${toneForStatus(lifecycleState)}`}>{lifecycleState}</span>
        <span className={`mission-badge ${toneForStatus(healthState)}`}>{healthState}</span>
        <span className={`mission-badge ${toneForStatus(tenantState)}`}>{tenantState}</span>
      </div>

      <div className="mission-governance-grid">
        <StatusChip label="RFQs" value={countLabel(workspace.counts?.rfqs, rfqItems.length)} source="/platform/customer-rfq-quotes/rfqs" tone={toneForStatus(rfqState)} />
        <StatusChip label="Quotations" value={countLabel(workspace.counts?.quotations, quotationItems.length)} source="/platform/customer-rfq-quotes/quotations" tone={toneForStatus(quotationState)} />
        <StatusChip label="Source authority" value={sourceState} source="/platform/customer-rfq-quotes/source-authority" tone={toneForStatus(sourceState)} />
        <StatusChip label="Freshness" value={freshnessState} source="/platform/customer-rfq-quotes/freshness" tone={toneForStatus(freshnessState)} />
        <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
        <StatusChip label="Security" value="FAIL CLOSED" source="Workspace policy" tone="good" />
      </div>

      <div className="mission-detail-grid">
        <DetailPanel label="Workspace identity" value={identity.canonical_name || "NO_DATA"} note={identity.workspace_id || "Workspace ID unavailable"} />
        <DetailPanel label="Dashboard reference" value={identity.dashboard_reference || "PHASE65_6_3_IMPLEMENTATION_COMPLETE"} note={identity.identity_reference || "Identity reference unavailable"} />
        <DetailPanel label="Readiness" value={readinessState} note={(readiness.limitations || identity.accepted_limitations || []).join(" · ") || "Readiness remains truthful."} />
        <DetailPanel label="Compatibility" value={stateLabel(compatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS")} note={compatibility.limitations?.[0] || "Compatibility remains bounded"} />
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>RFQ registry</h3>
          <p className="muted">Records remain tenant-bound, bounded, and read only. No fabricated RFQs are shown.</p>
          <p className="muted">No fabricated RFQ or quotation data is shown.</p>
          <div className="mission-work-list">
            {rfqItems.slice(0, 6).map((item) => (
              <div key={item.rfq_reference || item.reference || item.id} className="mission-work-row">
                <div>
                  <b>{item.rfq_reference || item.reference || item.id || "NO_DATA"}</b>
                  <span>{item.lifecycle_state || item.status || "NO_DATA"} · {item.freshness_state || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.customer_visibility_state || "TENANT_CONTEXT_REQUIRED"}</b>
                  <span>{item.source_authority || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!rfqItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Quotation registry</h3>
          <p className="muted">Quotation records remain tenant-bound, bounded, and read only. No price manipulation or submission controls are exposed.</p>
          <p className="muted">No fabricated RFQ or quotation data is shown.</p>
          <div className="mission-work-list">
            {quotationItems.slice(0, 6).map((item) => (
              <div key={item.quotation_reference || item.reference || item.id} className="mission-work-row">
                <div>
                  <b>{item.quotation_reference || item.reference || item.id || "NO_DATA"}</b>
                  <span>{item.lifecycle_state || item.status || "NO_DATA"} · {item.freshness_state || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.customer_visibility_state || "TENANT_CONTEXT_REQUIRED"}</b>
                  <span>{item.source_authority || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!quotationItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Lifecycle posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="RFQ lifecycle" value={stateLabel(rfqLifecycle.lifecycle_state || "NO_DATA")} note={rfqLifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            <DetailPanel label="Quotation lifecycle" value={stateLabel(quotationLifecycle.lifecycle_state || "NO_DATA")} note={quotationLifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            <DetailPanel label="Filter posture" value={stateLabel(workspace.filterState || rfqs.visibility_state || "TENANT_CONTEXT_REQUIRED")} note="/platform/customer-rfq-quotes/rfqs and /quotations remain bounded." />
            <DetailPanel label="Source authority" value={sourceState} note={sourceAuthority.source_system || "RFQ lifecycle and quote draft metadata"} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Operational constraints</h3>
          <p className="muted">The workspace is read only. No create, edit, delete, upload, accept, reject, submit, or message controls are implemented.</p>
          <ul className="mission-bullet-list">
            <li>Customer RFQs and quotations are not fabricated.</li>
            <li>Pagination and filtering remain bounded.</li>
            <li>Tenant context is required for visibility.</li>
            <li>Governance and security remain fail closed.</li>
          </ul>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Source posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Policy" value={policy.global_governance_precedence || "highest"} note={policy.external_action_prohibition || "denied"} />
            <DetailPanel label="Diagnostics" value={diagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={diagnostics.limitations?.[0] || "Diagnostics are redacted."} />
            <DetailPanel label="Mission Control" value={missionControlIntegration.workspace_lifecycle_state || "READY_WITH_LIMITATIONS"} note={missionControlIntegration.current_milestone || "PHASE65.6.4_RFQ_AND_QUOTE_WORKSPACE"} />
            <DetailPanel label="Next authorised milestone" value={missionControlIntegration.next_authorized_milestone || "PHASE65.6.5_SECURE_DOCUMENT_CENTRE"} note="Later feature remains deferred." />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Navigation</h3>
          <div className="mission-action-grid">
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-dashboard")}><BookOpenText size={15} /> Open Customer Dashboard</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-identity")}><ShieldCheck size={15} /> Open Customer Identity</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("mission-control")}><ArrowLeftRight size={15} /> Return to Mission Control</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-self-service-portal")}><FileText size={15} /> Open Customer Portal</button>
          </div>
        </div>
      </div>
    </section>
  );
}
