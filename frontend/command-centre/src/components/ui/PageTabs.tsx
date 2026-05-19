export default function PageTabs({ activePage, tabs, onChange }) {
  return (
    <div className="glass-card flex flex-wrap items-center gap-3 rounded-3xl p-4">
      {tabs.map((tab) => {
        const active = tab.key === activePage;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={[
              "rounded-2xl border px-4 py-3 text-left transition-all",
              active
                ? "border-command-green/70 bg-command-green/15 text-white shadow-glow"
                : "border-slate-700/60 bg-slate-950/45 text-slate-300 hover:border-slate-500/80 hover:bg-slate-900/70",
            ].join(" ")}
          >
            <div className="text-sm font-black uppercase tracking-[.22em]">{tab.label}</div>
            <div className="mt-1 text-xs text-slate-400">{tab.description}</div>
          </button>
        );
      })}
    </div>
  );
}
