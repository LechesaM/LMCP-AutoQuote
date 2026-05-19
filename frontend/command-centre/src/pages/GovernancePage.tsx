import GovernanceRulesGrid from "../components/governance/GovernanceRulesGrid.tsx";
import { rfqRules } from "../utils/tenderFilters";

export default function GovernancePage() {
  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Governance and Release Controls</h2>
        <p className="mt-2 text-sm text-slate-400">The command centre keeps manual approval, review_ready, proof capture and final submission under human control.</p>
      </div>
      <GovernanceRulesGrid />
      <div className="glass-card rounded-3xl p-5">
        <h3 className="text-lg font-black text-white">Preserved Rules</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {rfqRules.map((rule) => (
            <div key={rule} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
              {rule}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
