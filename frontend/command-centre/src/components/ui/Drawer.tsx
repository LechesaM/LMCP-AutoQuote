import { X } from "lucide-react";
import { type ReactNode, useEffect } from "react";

type DrawerProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
};

export default function Drawer({ open, title, subtitle, onClose, children }: DrawerProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    if (open) {
      window.addEventListener("keydown", handleKeyDown);
    }

    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50">
      <button aria-label="Close drawer overlay" className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onClose} type="button" />
      <aside className="absolute right-0 top-0 h-full w-full max-w-3xl overflow-y-auto border-l border-slate-700/40 bg-[#06111f] p-5 shadow-[0_0_120px_rgba(0,0,0,.55)] md:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-black uppercase tracking-[.28em] text-command-cyan">Read-only detail</div>
            <h2 className="mt-1 text-2xl font-black text-white">{title}</h2>
            {subtitle ? <p className="mt-2 text-sm text-slate-400">{subtitle}</p> : null}
          </div>
          <button
            aria-label="Close drawer"
            className="rounded-2xl border border-slate-700/60 bg-slate-950/60 p-2 text-slate-300 transition hover:border-command-cyan/40 hover:text-white"
            onClick={onClose}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-6">{children}</div>
      </aside>
    </div>
  );
}
