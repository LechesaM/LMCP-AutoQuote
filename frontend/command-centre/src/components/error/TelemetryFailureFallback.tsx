import { ShieldAlert, RefreshCcw } from "lucide-react";

export default function TelemetryFailureFallback({ error, onReset }) {
  return (
    <div className="glass-card rounded-3xl p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-command-amber/15 text-command-amber">
          <ShieldAlert size={20} />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-black text-white">Telemetry temporarily unavailable</h3>
          <p className="mt-1 text-sm text-slate-400">
            The live telemetry feed failed to render. Operator workflow, governance, and review controls remain available.
          </p>
          {error ? <p className="mt-2 text-xs text-slate-500">{String(error.message || error)}</p> : null}
        </div>
      </div>
      {onReset ? (
        <button
          type="button"
          onClick={onReset}
          className="mt-5 inline-flex items-center gap-2 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
        >
          <RefreshCcw size={16} />
          Retry telemetry
        </button>
      ) : null}
    </div>
  );
}
