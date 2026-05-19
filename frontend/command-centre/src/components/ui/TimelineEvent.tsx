import { Clock3, ShieldAlert, ShieldCheck } from "lucide-react";

export default function TimelineEvent({ event }) {
  const tone =
    event?.severity === "critical"
      ? "text-command-red border-command-red/30 bg-command-red/10"
      : event?.severity === "warning"
        ? "text-command-amber border-command-amber/30 bg-command-amber/10"
        : "text-command-cyan border-command-cyan/30 bg-command-cyan/10";

  return (
    <div className={`rounded-2xl border p-4 ${tone}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] opacity-80">
            {event?.severity === "critical" ? <ShieldAlert size={13} /> : event?.severity === "warning" ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
            {event?.eventType || "operator_event"}
          </div>
          <div className="mt-2 text-sm font-bold text-white">{event?.title || "Operator event"}</div>
          {event?.tenderId ? <div className="mt-1 text-xs text-slate-300">{event.tenderId}</div> : null}
        </div>
        <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.24em] text-slate-400">
          <Clock3 size={12} />
          {event?.createdAt || "unknown"}
        </div>
      </div>
    </div>
  );
}
