import StateBadge from "./ui/StateBadge.tsx";
import { SkeletonCard } from "./ui/SkeletonBlocks.tsx";

export default function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = "green",
  state = "ready",
  description = "",
  onRetry,
}) {
  const cls =
    accent === "cyan"
      ? "text-command-cyan bg-command-cyan/10"
      : accent === "amber"
        ? "text-command-amber bg-command-amber/10"
        : accent === "red"
          ? "text-command-red bg-command-red/10"
          : "text-command-green bg-command-green/10";

  if (state === "loading") {
    return (
      <div className="glass-card rounded-3xl p-5">
        <SkeletonCard lines={2} />
      </div>
    );
  }

  return (
    <div className={`glass-card rounded-3xl p-5 ${state === "stale" ? "opacity-85" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.22em] text-slate-500">
            <span>{title}</span>
            {state !== "ready" ? <StateBadge state={state} /> : null}
          </div>
          <div className="mt-3 text-3xl font-black tracking-tight text-white">
            {state === "error" ? "—" : state === "empty" ? "No data" : value}
          </div>
          <div className="mt-1 text-sm text-slate-400">
            {state === "error" ? description || "Metric unavailable" : subtitle}
          </div>
        </div>
        {Icon ? (
          <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${cls}`}>
            {state === "error" ? <span className="text-lg font-black">!</span> : <Icon size={22} />}
          </div>
        ) : null}
      </div>
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
