import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import NotificationToast from "../ui/NotificationToast.tsx";

export default function OperatorEscalationPanel({ notifications = [], assignments = [] }) {
  const overdue = assignments.filter((item) => String(item.status || "").toLowerCase() === "overdue").length;
  const critical = notifications.filter((item) => String(item.severity || "").toLowerCase() === "critical").length;
  const warnings = notifications.filter((item) => String(item.severity || "").toLowerCase() === "warning").length;

  return (
    <SectionPanel title="Escalation Panel" description="Advisory escalation recommendations only." state={critical > 0 ? "stale" : "ready"}>
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Overdue Reviews" value={overdue} tone="red" />
        <TelemetryStat label="Critical Alerts" value={critical} tone="red" />
        <TelemetryStat label="Warnings" value={warnings} tone="amber" />
      </div>

      <div className="mt-4 space-y-3">
        {notifications.slice(0, 3).map((notification) => (
          <NotificationToast key={notification.notificationId} notification={notification} />
        ))}
        {!notifications.length ? <div className="text-sm text-slate-400">No active escalation events.</div> : null}
      </div>
    </SectionPanel>
  );
}
