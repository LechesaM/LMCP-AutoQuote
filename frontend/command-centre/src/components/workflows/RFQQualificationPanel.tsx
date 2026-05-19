import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";

function listFrom(value, fallback = []) {
  return Array.isArray(value) ? value : fallback;
}

export default function RFQQualificationPanel({ qualification = {}, row = {} }) {
  const readiness = String(qualification.readiness_state || qualification.readinessState || row.reviewStatus || "unknown");
  const recommendation = String(qualification.recommendation || row.qualificationState || "MANUAL_REVIEW");
  const riskBreakdown = qualification.risk_breakdown || qualification.riskBreakdown || {};
  const languagePatterns = listFrom(qualification.detected_language_patterns || qualification.detectedLanguagePatterns);
  const complianceRequirements = listFrom(qualification.compliance_requirements || qualification.complianceRequirements);
  const supplierMatch = qualification.supplier_match || qualification.supplierMatch || {};
  const nextAction = String(qualification.next_operator_action || qualification.nextOperatorAction || "Review manually");

  return (
    <SectionPanel title="Qualification Summary" description="Read-only qualification intelligence and operator guidance." state={readiness === "READY" ? "ready" : readiness === "MANUAL_ONLY" ? "stale" : "refreshing"}>
      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={recommendation === "GO" ? "ready" : recommendation === "REJECT" ? "error" : "stale"} />
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          Readiness {readiness}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Qualification Score" value={Number(qualification.qualification_score ?? qualification.qualificationScore ?? 0).toFixed(1)} tone="cyan" />
        <TelemetryStat label="Risk Score" value={Number(qualification.risk_score ?? qualification.riskScore ?? riskBreakdown.overall_risk ?? 0).toFixed(1)} tone="amber" />
        <TelemetryStat label="Supplier Match" value={Number(supplierMatch.supplier_match_score ?? supplierMatch.supplierMatchScore ?? 0).toFixed(1)} tone="green" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Risk Breakdown</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {Object.entries(riskBreakdown).length ? (
              Object.entries(riskBreakdown).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-4">
                  <span className="capitalize text-slate-400">{key.replace(/_/g, " ")}</span>
                  <span className="font-bold text-white">{String(value)}</span>
                </div>
              ))
            ) : (
              <div>No risk breakdown available.</div>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Detected Language Patterns</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {languagePatterns.length ? (
              languagePatterns.map((pattern, index) => (
                <span key={`${pattern}-${index}`} className="rounded-full border border-command-cyan/30 bg-command-cyan/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.2em] text-command-cyan">
                  {String(pattern)}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-400">No detected patterns.</span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Compliance Requirements</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {complianceRequirements.length ? (
              complianceRequirements.map((item, index) => (
                <span key={`${item}-${index}`} className="rounded-full border border-command-green/30 bg-command-green/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.2em] text-command-green">
                  {String(item)}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-400">No compliance matrix available.</span>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Supplier Domain Match</div>
          <div className="mt-3 text-sm text-slate-300">
            <div className="font-bold text-white">{String(supplierMatch.supplier_domain || supplierMatch.supplierDomain || "Unknown")}</div>
            <div className="mt-2 text-slate-400">{nextAction}</div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-command-cyan/30 bg-command-cyan/10 p-4 text-sm text-slate-200">
        Recommendation: <span className="font-black text-white">{recommendation}</span>. Next operator action: <span className="font-black text-white">{nextAction}</span>.
      </div>
    </SectionPanel>
  );
}
