import Drawer from "../ui/Drawer.tsx";
import TimelineEvent from "../ui/TimelineEvent.tsx";

export default function OperatorAuditDrawer({ open, event, onClose }) {
  return (
    <Drawer open={open} onClose={onClose} subtitle="Append-only audit and event detail" title={event?.title || event?.eventType || "Operator Audit"}>
      {event ? (
        <div className="space-y-4">
          <TimelineEvent event={event} />
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
              <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Operator</div>
              <div className="mt-2 font-bold text-white">{event.operatorId || "—"}</div>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
              <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">RFQ</div>
              <div className="mt-2 font-bold text-white">{event.tenderId || "—"}</div>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
            <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Event details</div>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-slate-200">{JSON.stringify(event.details || {}, null, 2)}</pre>
          </div>
          <div className="rounded-2xl border border-command-green/30 bg-command-green/10 px-4 py-3 text-sm text-slate-200">
            This timeline is append-only, reviewable and does not bypass workflow governance.
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
