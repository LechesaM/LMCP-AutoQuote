import { useMemo, useState } from "react";
import OperatorActionPanel from "../components/operator/OperatorActionPanel.tsx";
import OperatorAssignmentTable from "../components/operator/OperatorAssignmentTable.tsx";
import OperatorCapacityPanel from "../components/operator/OperatorCapacityPanel.tsx";
import OperatorNotificationsPanel from "../components/operator/OperatorNotificationsPanel.tsx";
import OperatorEscalationPanel from "../components/operator/OperatorEscalationPanel.tsx";
import OperatorTimeline from "../components/operator/OperatorTimeline.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import useOperatorActions from "../hooks/useOperatorActions";
import useOperatorAssignments from "../hooks/useOperatorAssignments";
import useOperatorNotifications from "../hooks/useOperatorNotifications";
import useOperatorTimeline from "../hooks/useOperatorTimeline";

export default function OperatorOperationsPage() {
  const actions = useOperatorActions();
  const assignments = useOperatorAssignments();
  const notifications = useOperatorNotifications();
  const timeline = useOperatorTimeline();
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const handleAction = async (action, payload) => {
    await actions.performAction(action, payload);
    await Promise.all([assignments.refresh(), notifications.refresh(), timeline.refresh()]);
  };

  const summary = useMemo(
    () => ({
      pending: assignments.assignments.filter((item) => String(item.status || "").toLowerCase() !== "assigned").length,
      overdue: assignments.assignments.filter((item) => String(item.status || "").toLowerCase() === "overdue").length,
      alerts: notifications.notifications.length,
      timeline: timeline.total,
    }),
    [assignments.assignments, notifications.notifications.length, timeline.total],
  );

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Operator Operations</h2>
        <p className="mt-2 text-sm text-slate-400">Controlled operator actions, assignment workflow, activity timelines and notifications remain manual and auditable.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Assigned" value={assignments.summary.activeAssignments} tone="cyan" />
        <TelemetryStat label="Pending" value={summary.pending} tone="green" />
        <TelemetryStat label="Overdue" value={summary.overdue} tone="red" />
        <TelemetryStat label="Alerts" value={summary.alerts} tone="amber" />
        <TelemetryStat label="Timeline Events" value={summary.timeline} tone="green" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <div className="space-y-6">
          <OperatorAssignmentTable snapshot={assignments} onSelectAssignment={setSelectedAssignment} selectedTenderId={selectedAssignment?.tenderId || ""} />
          <OperatorActionPanel loading={actions.loading} onAction={handleAction} selectedRFQ={selectedAssignment || assignments.assignments[0] || {}} />
          <OperatorTimeline snapshot={timeline} onSelectEvent={setSelectedEvent} />
        </div>

        <div className="space-y-6">
          <OperatorCapacityPanel
            snapshot={
              assignments.capacity
                ? {
                    ...assignments.capacity,
                    loading: assignments.loading,
                    refreshing: assignments.refreshing,
                    error: assignments.error,
                    stale: assignments.dataSource !== "runtime",
                    dataSource: assignments.dataSource,
                    generatedAt: assignments.generatedAt,
                    refresh: assignments.refresh,
                  }
                : null
            }
          />
          <OperatorNotificationsPanel snapshot={notifications} />
          <OperatorEscalationPanel assignments={assignments.assignments} notifications={notifications.notifications} />
        </div>
      </div>

      {selectedEvent ? (
        <div className="glass-card rounded-3xl p-5">
          <div className="text-sm font-black uppercase tracking-[.24em] text-command-cyan">Selected Timeline Event</div>
          <pre className="mt-4 overflow-x-auto rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-xs text-slate-300">{JSON.stringify(selectedEvent, null, 2)}</pre>
        </div>
      ) : null}
    </div>
  );
}
