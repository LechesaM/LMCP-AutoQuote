import { BarChart3, RefreshCcw } from "lucide-react";

export default function ChartFallback({ error, onReset, title = "Chart unavailable" }) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-700/70 bg-slate-950/40 p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-command-cyan/15 text-command-cyan">
          <BarChart3 size={18} />
        </div>
        <div className="flex-1">
          <h4 className="text-base font-black text-white">{title}</h4>
          <p className="mt-1 text-sm text-slate-400">
            This chart could not render. The rest of the dashboard remains operational.
          </p>
          {error ? <p className="mt-2 text-xs text-slate-500">{String(error.message || error)}</p> : null}
        </div>
      </div>
      {onReset ? (
        <button
          type="button"
          onClick={onReset}
          className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
        >
          <RefreshCcw size={16} />
          Reload chart
        </button>
      ) : null}
    </div>
  );
}
