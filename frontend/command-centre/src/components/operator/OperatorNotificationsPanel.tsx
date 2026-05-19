import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import NotificationToast from "../ui/NotificationToast.tsx";
import { useOperatorNotifications } from "../../hooks/useOperatorNotifications";

export default function OperatorNotificationsPanel({ snapshot = null }) {
  const live = useOperatorNotifications();
  const { notifications, loading, refreshing, error, dataSource, refresh } = snapshot || live;
  const state = loading ? "loading" : error ? "error" : refreshing ? "refreshing" : dataSource !== "runtime" ? "stale" : "ready";

  return (
    <SectionPanel
      title="Operator Notifications"
      description="Advisory alerts for stale RFQs, source failures, queue overload and governance warnings."
      state={state}
      actions={
        <div className="flex items-center gap-2">
          <StateBadge state={dataSource === "runtime" ? "ready" : "stale"} />
          <button className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.22em] text-slate-300" onClick={refresh} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <div className="space-y-3">
        {notifications.length ? notifications.map((notification) => <NotificationToast key={notification.notificationId} notification={notification} />) : <div className="text-sm text-slate-400">No active notifications.</div>}
      </div>
    </SectionPanel>
  );
}
