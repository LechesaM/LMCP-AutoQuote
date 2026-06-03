import GovernanceRulesGrid from "../components/governance/GovernanceRulesGrid.tsx";
import { rfqRules } from "../utils/tenderFilters";

export default function GovernancePage() {
  return (
    <div className="space-y-6">
      <div className="glass-card min-w-0 rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Governance and Release Controls</h2>
        <p className="mt-2 text-sm text-slate-400">The command centre keeps manual approval, review_ready, proof capture and final submission under human control.</p>
      </div>
      <GovernanceRulesGrid />
      <div className="glass-card min-w-0 rounded-3xl p-5">
        <h3 className="text-lg font-black text-white">Manual Completion and Proof</h3>
        <p className="mt-2 max-w-4xl text-sm text-slate-400">
          The local workflow stays operator-led at the end of the chain: prepare the pack, capture the manual completion record, generate proof, and keep final portal submission blocked unless a human uploads it.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <a
            href="/quote-compilation/status"
            className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-command-cyan/60 hover:text-white"
          >
            Quote Compilation Status
          </a>
          <a
            href="/submission-proof/status"
            className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-command-cyan/60 hover:text-white"
          >
            Submission Proof Status
          </a>
          <a
            href="/portal-submission/status"
            className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-command-cyan/60 hover:text-white"
          >
            Portal Submission Status
          </a>
        </div>
      </div>
      <div className="glass-card min-w-0 rounded-3xl p-5">
        <h3 className="text-lg font-black text-white">Preserved Rules</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {rfqRules.map((rule) => (
            <div key={rule} className="min-w-0 rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
              {rule}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
