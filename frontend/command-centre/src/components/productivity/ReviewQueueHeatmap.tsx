import SectionPanel from "../ui/SectionPanel.tsx";

export default function ReviewQueueHeatmap({ heatmap = [], operatorDistribution = {}, sourceDistribution = {}, escalationDensity = {}, provinceDensity = {} }) {
  return (
    <SectionPanel title="Queue Heatmap" description="Age, operator distribution, escalation density and source concentration." state={heatmap.length ? "ready" : "empty"}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {heatmap.slice(0, 9).map((item, index) => (
          <div key={`${item.axis}-${item.label}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-500">{item.axis}</div>
            <div className="mt-2 text-lg font-black text-white">{item.label}</div>
            <div className="mt-1 text-3xl font-black text-command-cyan">{item.value}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        <MiniMap title="Operators" data={operatorDistribution} />
        <MiniMap title="Sources" data={sourceDistribution} />
        <MiniMap title="Escalations" data={escalationDensity} />
        <MiniMap title="Provinces" data={provinceDensity} />
      </div>
    </SectionPanel>
  );
}

function MiniMap({ title, data = {} }) {
  const entries = Object.entries(data).slice(0, 6);
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
      <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">{title}</div>
      <div className="mt-3 space-y-2">
        {entries.length ? entries.map(([label, value]) => <Row key={label} label={label} value={value} />) : <div className="text-sm text-slate-500">No data</div>}
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-800/70 bg-slate-950/55 px-3 py-2">
      <div className="text-sm text-slate-300">{label}</div>
      <div className="text-sm font-black text-white">{value}</div>
    </div>
  );
}

