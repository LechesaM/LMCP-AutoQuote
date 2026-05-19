import { LoaderCircle } from "lucide-react";

export default function RouteLoadingState({ label = "Loading route" }) {
  return (
    <div className="glass-card rounded-3xl p-6">
      <div className="flex items-center gap-3 text-command-cyan">
        <LoaderCircle size={18} className="animate-spin" />
        <span className="text-xs font-black uppercase tracking-[.22em]">{label}</span>
      </div>
      <div className="mt-4 space-y-3">
        <div className="h-4 w-3/4 rounded-full bg-slate-800/70" />
        <div className="h-4 w-2/3 rounded-full bg-slate-800/70" />
        <div className="h-4 w-1/2 rounded-full bg-slate-800/70" />
      </div>
    </div>
  );
}
