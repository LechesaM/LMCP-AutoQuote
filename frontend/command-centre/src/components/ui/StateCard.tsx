export default function StateCard({
  title,
  state = "ready",
  children,
  description = "",
  onRetry,
}) {
  const stateLabel = {
    loading: "Loading",
    error: "Error",
    empty: "Empty",
    stale: "Stale",
    refreshing: "Refreshing",
    ready: "",
  }[state];

  return (
    <div className="glass-card rounded-3xl p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-black text-white">{title}</h3>
          {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
        </div>
        {state !== "ready" ? (
          <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
            {stateLabel}
          </div>
        ) : null}
      </div>
      <div className="mt-4">{children}</div>
      {state === "error" && onRetry ? (
        <button
          onClick={onRetry}
          className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
