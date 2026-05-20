import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import ActionBadge from "../ui/ActionBadge.tsx";

export default function GovernanceRiskPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const risks = Array.isArray(data?.riskRegister?.risks) ? data.riskRegister.risks : Array.isArray(data?.riskRegister?.risk_register?.risks) ? data.riskRegister.risk_register.risks : [];
  return (
    <SectionPanel title="Governance Risk Register" description="Enterprise governance and compliance risk overview." state={state}>
      {risks.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {risks.map((risk: any, index: number) => (
            <div key={`${risk.risk || index}`} className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-black text-white">{risk.risk || "risk"}</div>
                  <div className="mt-1 text-sm text-slate-400">{risk.description || ""}</div>
                </div>
                <ActionBadge action={risk.severity || "low"} tone={risk.severity === "critical" ? "red" : risk.severity === "high" ? "amber" : "cyan"} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyTelemetryState title="No active governance risks" description="Current governance controls are not flagging a new risk register item." />
      )}
    </SectionPanel>
  );
}
