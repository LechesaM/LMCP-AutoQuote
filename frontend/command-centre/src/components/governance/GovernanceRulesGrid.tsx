import { rfqRules } from "../../utils/tenderFilters";

export default function GovernanceRulesGrid() {
  return (
    <section className="glass-card rounded-3xl p-5">
      <h3 className="text-lg font-black text-white">RFQ Qualification Rules</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {rfqRules.map((rule) => (
          <div key={rule} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3 text-sm text-slate-300">
            {rule}
          </div>
        ))}
      </div>
    </section>
  );
}
