import { useState } from "react";
import OperatorAssignmentTable from "../components/operator/OperatorAssignmentTable.tsx";
import OperatorCapacityPanel from "../components/operator/OperatorCapacityPanel.tsx";
import OperatorEscalationPanel from "../components/operator/OperatorEscalationPanel.tsx";
import OperatorAuditDrawer from "../components/operator/OperatorAuditDrawer.tsx";
import OperatorNotificationsPanel from "../components/operator/OperatorNotificationsPanel.tsx";
import TelemetryStat from "../components/ui/TelemetryStat.tsx";
import useOperatorAssignments from "../hooks/useOperatorAssignments";
import useOperatorNotifications from "../hooks/useOperatorNotifications";

export default function OperatorAssignmentsPage() {
  const assignments = useOperatorAssignments();
  const notifications = useOperatorNotifications();
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [selectedAudit, setSelectedAudit] = useState(null);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-5">
        <h2 className="text-xl font-black text-white">Operator Assignments</h2>
        <p className="mt-2 text-sm text-slate-400">Assignment queues, workload balancing, and escalation recommendations remain operator-governed and reversible.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Active Assignments" value={assignments.summary.activeAssignments} tone="cyan" />
        <TelemetryStat label="Operators" value={assignments.summary.operators} tone="green" />
        <TelemetryStat label="Capacity" value={assignments.summary.capacity} tone="amber" />
        <TelemetryStat label="Notifications" value={notifications.notifications.length} tone="red" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <div className="space-y-6">
          <OperatorAssignmentTable snapshot={assignments} onSelectAssignment={(row) => { setSelectedAssignment(row); setSelectedAudit(row); }} selectedTenderId={selectedAssignment?.tenderId || ""} />
          <div className="glass-card rounded-3xl p-5">
            <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Selected Assignment</div>
            <pre className="mt-4 overflow-x-auto rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-xs text-slate-300">{JSON.stringify(selectedAssignment || {}, null, 2)}</pre>
          </div>
        </div>

        <div className="space-y-6">
          <OperatorCapacityPanel
            snapshot={{
              ...assignments.capacity,
              loading: assignments.loading,
              refreshing: assignments.refreshing,
              error: assignments.error,
              stale: assignments.dataSource !== "runtime",
              dataSource: assignments.dataSource,
              generatedAt: assignments.generatedAt,
              refresh: assignments.refresh,
            }}
          />
          <OperatorEscalationPanel assignments={assignments.assignments} notifications={notifications.notifications} />
          <OperatorNotificationsPanel snapshot={notifications} />
        </div>
      </div>

      <OperatorAuditDrawer
        event={
          selectedAudit
            ? {
                eventId: selectedAudit.assignmentId,
                eventType: "operator_assignment",
                operatorId: selectedAudit.operatorId,
                tenderId: selectedAudit.tenderId,
                title: "Operator assignment",
                severity: selectedAudit.status === "overdue" ? "warning" : "info",
                reversible: true,
                reviewable: true,
                createdAt: selectedAudit.assignedAt,
                details: selectedAudit.details,
              }
            : null
        }
        open={Boolean(selectedAudit)}
        onClose={() => setSelectedAudit(null)}
      />
    </div>
  );
}
