import { decisionPackData } from "../data/decisionPackData";

function Pill({ children, tone = "slate" }) {
  const tones = {
    slate: "border-white/10 bg-white/5 text-slate-200",
    green: "border-emerald-500/20 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-500/20 bg-amber-500/10 text-amber-200",
  };
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tones[tone] || tones.slate}`}>{children}</span>;
}

export default function DecisionPackWorkspace() {
  const provinces = [
    { key: "Gauteng", title: "Gauteng", items: decisionPackData.provinceShortlists.Gauteng },
    { key: "WesternCape", title: "Western Cape", items: decisionPackData.provinceShortlists.WesternCape },
    { key: "KwaZuluNatal", title: "KwaZulu-Natal", items: decisionPackData.provinceShortlists.KwaZuluNatal },
    { key: "Mpumalanga", title: "Mpumalanga", items: decisionPackData.provinceShortlists.Mpumalanga },
  ];

  return (
    <section className="space-y-6">
      <header className="rounded-[28px] border border-white/10 bg-slate-900/85 p-6 shadow-2xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">Advisory Layer</div>
            <h1 className="mt-2 text-3xl font-semibold text-white">Decision Pack</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              A read-only synthesis of the playbook, category scoring summary, and province target views. This page is advisory only and does not alter the certified workflow.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill tone="green">Read Only</Pill>
            <Pill tone="amber">Manual Review</Pill>
            <Pill>Frozen Repository</Pill>
          </div>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <article className="rounded-[24px] border border-white/10 bg-white/5 p-5">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Top Priority</div>
          <h2 className="mt-2 text-xl font-semibold text-white">PPE</h2>
          <p className="mt-2 text-sm text-slate-300">Highest combined score and broad supplier coverage.</p>
        </article>
        <article className="rounded-[24px] border border-white/10 bg-white/5 p-5">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Best Province Fit</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Cleaning materials</h2>
          <p className="mt-2 text-sm text-slate-300">Strong fit across Gauteng, Western Cape, Mpumalanga, and KwaZulu-Natal.</p>
        </article>
        <article className="rounded-[24px] border border-white/10 bg-white/5 p-5">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Decision Rule</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Blocked categories stay out</h2>
          <p className="mt-2 text-sm text-slate-300">Medical consumables, IT equipment, diesel, petrol, catering, and briefing-heavy tenders remain excluded.</p>
        </article>
      </div>

      <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">Decision Rules</div>
            <h2 className="mt-2 text-2xl font-semibold text-white">Operator Guidance</h2>
          </div>
          <Pill tone="amber">Advisory Only</Pill>
        </div>
        <div className="mt-5 grid gap-3">
          {decisionPackData.decisionRules.map((rule) => (
            <div key={rule} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              {rule}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">Top Overall Categories</div>
            <h2 className="mt-2 text-2xl font-semibold text-white">Advisory Ranking</h2>
          </div>
        </div>
        <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-white/5 text-slate-300">
              <tr>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {decisionPackData.topOverallCategories.map((item) => (
                <tr key={item.category} className="border-t border-white/10 bg-slate-950/30">
                  <td className="px-4 py-3 text-white">{item.category}</td>
                  <td className="px-4 py-3">
                    <Pill tone={item.action === "TARGET_IMMEDIATELY" ? "green" : "amber"}>{item.action}</Pill>
                  </td>
                  <td className="px-4 py-3 text-slate-300">{item.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {provinces.map((province) => (
          <article key={province.key} className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">{province.title}</div>
                <h2 className="mt-2 text-2xl font-semibold text-white">Top Five Targets</h2>
              </div>
            </div>
            <ol className="mt-5 space-y-3">
              {province.items.map((item, index) => (
                <li key={item} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                  <span className="text-sm font-medium text-white">{index + 1}. {item}</span>
                  <Pill>{province.title}</Pill>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </section>
    </section>
  );
}
