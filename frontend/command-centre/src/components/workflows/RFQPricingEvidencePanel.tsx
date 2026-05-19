import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";

function renderChain(chain) {
  if (!Array.isArray(chain) || !chain.length) {
    return <span className="text-sm text-slate-400">No traceability chain available.</span>;
  }
  return (
    <div className="space-y-2">
      {chain.map((entry, index) => (
        <div key={typeof entry === "string" ? `${entry}-${index}` : `${entry?.source || "entry"}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
          {typeof entry === "string" ? entry : JSON.stringify(entry)}
        </div>
      ))}
    </div>
  );
}

export default function RFQPricingEvidencePanel({ pricingEvidence = {}, pricingValidation = {}, pricingTraceability = {}, row = {} }) {
  const evidenceCompleteness = Number(pricingEvidence.evidence_completeness_score ?? pricingEvidence.evidenceCompletenessScore ?? row.pricingConfidence ?? 0);
  const defensibility = Number(pricingEvidence.pricing_defensibility_score ?? pricingEvidence.pricingDefensibilityScore ?? row.pricingConfidence ?? 0);
  const confidence = Number(pricingEvidence.pricing_confidence_score ?? pricingEvidence.pricingConfidenceScore ?? row.pricingConfidence ?? 0);
  const quoteAgeDays = Number(pricingEvidence.quote_age_days ?? pricingEvidence.quoteAgeDays ?? 0);
  const anomalies = pricingValidation.validation_errors || pricingValidation.validationErrors || [];
  const warnings = pricingValidation.validation_warnings || pricingValidation.validationWarnings || [];
  const traceabilityChain = pricingTraceability.traceability_chain || pricingTraceability.traceabilityChain || pricingEvidence.traceability_chain || pricingEvidence.traceabilityChain || [];
  const overrideNotes = String(pricingTraceability.operator_override_notes || pricingTraceability.operatorOverrideNotes || pricingEvidence.operator_override_notes || pricingEvidence.operatorOverrideNotes || "");

  return (
    <SectionPanel title="Pricing Evidence" description="Supplier evidence completeness, price defensibility and traceability." state={quoteAgeDays > 30 ? "stale" : "ready"}>
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={confidence > 70 ? "ready" : confidence > 50 ? "stale" : "error"} />
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Quote age {quoteAgeDays} days
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Evidence Completeness" value={evidenceCompleteness.toFixed(1)} tone="cyan" />
        <TelemetryStat label="Pricing Defensibility" value={defensibility.toFixed(1)} tone="green" />
        <TelemetryStat label="Pricing Confidence" value={confidence.toFixed(1)} tone={confidence > 70 ? "green" : confidence > 50 ? "amber" : "red"} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Validation Findings</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {warnings.length ? warnings.map((item, index) => <div key={`${item}-${index}`}>• {String(item)}</div>) : <div>No pricing warnings.</div>}
            {anomalies.length ? anomalies.map((item, index) => <div key={`${item}-${index}`} className="text-command-amber">• {String(item)}</div>) : null}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Operator Notes</div>
          <div className="mt-3 text-sm text-slate-300">{overrideNotes || "No operator override notes captured."}</div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
        <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Traceability Chain</div>
        <div className="mt-3">{renderChain(traceabilityChain)}</div>
      </div>
    </SectionPanel>
  );
}
