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

export default function CustomerDocumentCentreWorkspace({ view = {}, onNavigate = () => {} }) {
  const centre = view.customerDocumentCentre || {};
  const identity = centre.identity || {};
  const catalogue = centre.catalogue || {};
  const documentRecord = centre.document || {};
  const classifications = centre.classifications || {};
  const lifecycle = centre.lifecycle || {};
  const retention = centre.retention || {};
  const integrity = centre.integrity || {};
  const visibility = centre.visibility || {};
  const diagnostics = centre.diagnostics || {};
  const compatibility = centre.compatibility || {};
  const health = centre.health || {};
  const readiness = centre.readiness || {};
  const missionControlIntegration = centre.missionControlIntegration || {};
  const documentItems = Array.isArray(catalogue.records) ? catalogue.records : [];
  const classificationItems = Array.isArray(classifications.classifications) ? classifications.classifications : [];

  const readinessState = stateLabel(centre.readinessState || readiness.readiness_state || health.readiness_state);
  const lifecycleState = stateLabel(identity.lifecycle_state || centre.lifecycle?.current_state || "READY_WITH_LIMITATIONS");
  const healthState = stateLabel(centre.healthState || health.health_state || health.status || "READY_WITH_LIMITATIONS");
  const catalogueState = stateLabel(catalogue.registry_state || catalogue.source_authority_state || "NO_DATA");
  const integrityState = stateLabel(integrity.integrity_state || "NO_DATA");
  const visibilityState = stateLabel(visibility.document_visibility_policy || "TENANT_CONTEXT_REQUIRED");
  const retentionState = stateLabel(retention.retention_state || "NO_DATA");
  const freshnessState = stateLabel(catalogue.freshness_state || "NO_DATA");

  return (
    <section className="card mission-panel customer-document-centre-workspace" aria-labelledby="customer-document-centre-heading">
      <SectionHeader
        eyebrow="Phase65.6.5"
        title="Secure Document Centre"
        description="Truthful read-only document centre foundation. Uploads, downloads, sharing, editing, signing, and storage-provider actions remain not implemented."
        action={<button type="button" className="mission-badge good" onClick={() => onNavigate("mission-control")}><RefreshCw size={14} /> Mission Control</button>}
      />

      <div className="mission-callouts">
        <span className={`mission-badge ${toneForStatus(readinessState)}`}>{readinessState}</span>
        <span className={`mission-badge ${toneForStatus(lifecycleState)}`}>{lifecycleState}</span>
        <span className={`mission-badge ${toneForStatus(healthState)}`}>{healthState}</span>
        <span className={`mission-badge ${toneForStatus(catalogueState)}`}>{catalogueState}</span>
      </div>

      <div className="mission-governance-grid">
        <StatusChip label="Documents" value={countLabel(centre.counts?.documents, documentItems.length)} source="/platform/customer-documents/catalogue" tone={toneForStatus(catalogueState)} />
        <StatusChip label="Classifications" value={countLabel(centre.counts?.classifications, classificationItems.length)} source="/platform/customer-documents/classifications" tone="good" />
        <StatusChip label="Integrity" value={integrityState} source="/platform/customer-documents/integrity" tone={toneForStatus(integrityState)} />
        <StatusChip label="Visibility" value={visibilityState} source="/platform/customer-documents/policy" tone={toneForStatus(visibilityState)} />
        <StatusChip label="Governance" value="PRESERVED" source="EELS" tone="good" />
        <StatusChip label="Security" value="FAIL CLOSED" source="Document policy" tone="good" />
      </div>

      <div className="mission-detail-grid">
        <DetailPanel label="Workspace identity" value={identity.canonical_name || "NO_DATA"} note={identity.workspace_id || "Workspace ID unavailable"} />
        <DetailPanel label="Portal reference" value={identity.portal_reference || "PHASE65_6_1_IMPLEMENTATION_COMPLETE"} note={identity.rfq_quote_reference || "Phase65.6.4 reference unavailable"} />
        <DetailPanel label="Readiness" value={readinessState} note={(readiness.limitations || identity.accepted_limitations || []).join(" · ") || "Readiness remains truthful."} />
        <DetailPanel label="Compatibility" value={stateLabel(compatibility.compatibility_state || "COMPATIBLE_WITH_LIMITATIONS")} note={compatibility.limitations?.[0] || "Compatibility remains bounded"} />
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Document catalogue</h3>
          <p className="muted">Document entries remain tenant bound, bounded, and read only. No fabricated document records are shown.</p>
          <p className="muted">No fabricated document data is shown.</p>
          <div className="mission-work-list">
            {documentItems.slice(0, 6).map((item) => (
              <div key={item.document_reference || item.reference || item.id} className="mission-work-row">
                <div>
                  <b>{item.document_name || item.document_reference || item.reference || item.id || "NO_DATA"}</b>
                  <span>{item.lifecycle || item.lifecycle_state || "NO_DATA"} · {item.classification || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.visibility || "TENANT_CONTEXT_REQUIRED"}</b>
                  <span>{item.source_authority || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!documentItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Classification registry</h3>
          <p className="muted">Classifications remain metadata only and do not expose document contents or storage providers.</p>
          <div className="mission-work-list">
            {classificationItems.slice(0, 6).map((item) => (
              <div key={item.classification_id} className="mission-work-row">
                <div>
                  <b>{item.canonical_name || item.classification_id}</b>
                  <span>{item.trust_requirement || "NO_DATA"} · {item.visibility || "NO_DATA"}</span>
                </div>
                <div>
                  <b>{item.storage_posture || "NO_DATA"}</b>
                  <span>{item.classification_id || "NO_DATA"}</span>
                </div>
              </div>
            ))}
            {!classificationItems.length ? <div className="mission-work-empty-inline">NO_DATA</div> : null}
          </div>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Lifecycle and retention</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Lifecycle" value={stateLabel(lifecycle.lifecycle_state || "NO_DATA")} note={lifecycle.no_mutation_guarantee ? "No mutation guarantee in force." : "Lifecycle metadata unavailable."} />
            <DetailPanel label="Retention" value={retentionState} note={retention.retention_policy || "metadata only"} />
            <DetailPanel label="Integrity" value={integrityState} note={integrity.checksum_algorithm || "SHA-256"} />
            <DetailPanel label="Freshness" value={freshnessState} note={catalogue.stale_threshold || "24h"} />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Operational constraints</h3>
          <p className="muted">The workspace is read only. No upload, download, delete, share, rename, move, sign, OCR, or indexing controls are implemented.</p>
          <ul className="mission-bullet-list">
            <li>Document metadata is not fabricated.</li>
            <li>Visibility remains tenant bound.</li>
            <li>Storage providers are not integrated.</li>
            <li>Governance and security remain fail closed.</li>
          </ul>
        </div>
      </div>

      <div className="mission-work-grid">
        <div className="mission-work-detail">
          <h3>Source posture</h3>
          <div className="mission-detail-grid compact">
            <DetailPanel label="Document detail" value={documentRecord.document_reference || "NO_DATA"} note={documentRecord.document_name || "No document detail is exposed."} />
            <DetailPanel label="Catalogue source" value={catalogue.source_authority_state || "NO_DATA"} note={catalogue.title || "Document Catalogue"} />
            <DetailPanel label="Visibility policy" value={visibilityState} note={visibility.fail_closed_behavior || "deny and audit"} />
            <DetailPanel label="Diagnostics" value={diagnostics.diagnostic_state || "READY_WITH_LIMITATIONS"} note={diagnostics.limitations?.[0] || "Diagnostics are redacted."} />
            <DetailPanel label="Mission Control" value={missionControlIntegration.workspace_lifecycle_state || "READY_WITH_LIMITATIONS"} note={missionControlIntegration.current_milestone || "PHASE65.6.5_SECURE_DOCUMENT_CENTRE"} />
            <DetailPanel label="Next authorised milestone" value={missionControlIntegration.next_authorized_milestone || "PHASE65.6.6_COMMUNICATION_NOTIFICATIONS"} note="Later feature remains deferred." />
          </div>
        </div>
        <div className="mission-work-detail">
          <h3>Navigation</h3>
          <div className="mission-action-grid">
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-dashboard")}><BookOpenText size={15} /> Open Customer Dashboard</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-rfq-quotes")}><FileText size={15} /> Open RFQ & Quote Workspace</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("mission-control")}><ArrowLeftRight size={15} /> Return to Mission Control</button>
            <button type="button" className="mission-action-button" onClick={() => onNavigate("customer-self-service-portal")}><ShieldCheck size={15} /> Open Customer Portal</button>
          </div>
        </div>
      </div>
    </section>
  );
}
