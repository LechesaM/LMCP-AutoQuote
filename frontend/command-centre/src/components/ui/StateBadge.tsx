export default function StateBadge({ state = "ready" }) {
  const palette = {
    loading: "border-command-cyan/40 bg-command-cyan/10 text-command-cyan",
    error: "border-command-red/40 bg-command-red/10 text-command-red",
    empty: "border-slate-700/60 bg-slate-950/55 text-slate-300",
    stale: "border-command-amber/40 bg-command-amber/10 text-command-amber",
    refreshing: "border-command-green/40 bg-command-green/10 text-command-green",
    ready: "border-command-green/30 bg-command-green/10 text-command-green",
  };

  return (
    <span className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] ${palette[state] || palette.ready}`}>
      {state}
    </span>
  );
}
