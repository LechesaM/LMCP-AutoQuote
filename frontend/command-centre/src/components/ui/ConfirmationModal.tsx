import { AlertTriangle, CheckCircle2, X } from "lucide-react";

export default function ConfirmationModal({ open, title, message, notePreview = "", confirmLabel = "Confirm", cancelLabel = "Cancel", onConfirm, onCancel, tone = "amber" }) {
  if (!open) {
    return null;
  }

  const accent =
    tone === "red"
      ? "border-command-red/40 bg-command-red/10 text-command-red"
      : tone === "green"
        ? "border-command-green/40 bg-command-green/10 text-command-green"
        : "border-command-amber/40 bg-command-amber/10 text-command-amber";

  return (
    <div className="fixed inset-0 z-[60]">
      <button aria-label="Close confirmation modal" className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onCancel} type="button" />
      <div className="absolute left-1/2 top-1/2 w-[min(92vw,36rem)] -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-slate-700/60 bg-[#06111f] p-5 shadow-[0_0_120px_rgba(0,0,0,.55)]">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${accent}`}>
              {tone === "green" ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
            </div>
            <div>
              <div className="text-xs font-black uppercase tracking-[.26em] text-slate-400">Explicit confirmation required</div>
              <h3 className="mt-1 text-xl font-black text-white">{title}</h3>
            </div>
          </div>
          <button className="rounded-2xl border border-slate-700/60 bg-slate-950/60 p-2 text-slate-300 transition hover:border-command-cyan/40 hover:text-white" onClick={onCancel} type="button">
            <X size={16} />
          </button>
        </div>

        <div className="mt-4 space-y-3 text-sm text-slate-300">
          <p>{message}</p>
          {notePreview ? (
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
              <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Audit note preview</div>
              <div className="mt-2 text-slate-200">{notePreview}</div>
            </div>
          ) : null}
          <div className="rounded-2xl border border-command-green/30 bg-command-green/10 px-4 py-3 text-command-green">
            Manual approval, review_ready and proof capture remain mandatory.
          </div>
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-2 text-sm font-bold text-slate-300" onClick={onCancel} type="button">
            {cancelLabel}
          </button>
          <button className={`rounded-2xl border px-4 py-2 text-sm font-bold ${tone === "red" ? "border-command-red/40 bg-command-red/10 text-command-red" : "border-command-green/40 bg-command-green/10 text-command-green"}`} onClick={onConfirm} type="button">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
