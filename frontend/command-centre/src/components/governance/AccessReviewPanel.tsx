import SectionPanel from "../ui/SectionPanel.tsx";
import EmptyTelemetryState from "../ui/EmptyTelemetryState.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { formatInteger } from "../../utils/formatters";

export default function AccessReviewPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const activeUsers = Array.isArray(data?.accessReview?.activeUsers) ? data.accessReview.activeUsers : Array.isArray(data?.accessReview?.active_users) ? data.accessReview.active_users : [];
  const staleSessions = Array.isArray(data?.accessReview?.staleSessions) ? data.accessReview.staleSessions : Array.isArray(data?.accessReview?.stale_sessions) ? data.accessReview.stale_sessions : [];
  const roleDistribution = data?.accessReview?.roleDistribution || data?.accessReview?.role_distribution || {};

  return (
    <SectionPanel title="Access Review" description="Active users, privileged access and stale session review." state={state}>
      <div className="grid gap-3 md:grid-cols-3">
        <TelemetryStat label="Active Users" value={formatInteger(activeUsers.length)} tone="cyan" />
        <TelemetryStat label="Stale Sessions" value={formatInteger(staleSessions.length)} tone={staleSessions.length ? "amber" : "green"} />
        <TelemetryStat label="Privileged Roles" value={formatInteger(Object.keys(roleDistribution).filter((key) => ["admin", "supervisor", "governance"].includes(String(key).toLowerCase())).length)} tone="amber" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Role distribution</div>
          <div className="mt-3 grid gap-2 text-sm text-slate-300">
            {Object.entries(roleDistribution).length ? Object.entries(roleDistribution).map(([role, count]) => <div key={role} className="flex items-center justify-between rounded-2xl border border-slate-700/60 bg-slate-900/45 px-3 py-2"><span>{role}</span><span>{formatInteger(count)}</span></div>) : <EmptyTelemetryState title="No role data" description="Role distribution is unavailable." />}
          </div>
        </div>
        <div className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Stale sessions</div>
          <div className="mt-3 grid gap-2 text-sm text-slate-300">
            {staleSessions.length ? staleSessions.map((session: any, index: number) => <div key={`${session.user_id || session.email || index}`} className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-3 py-2"><div className="font-bold text-white">{session.email || session.user_id}</div><div className="text-xs text-slate-400">{session.role}</div></div>) : <EmptyTelemetryState title="No stale sessions" description="Access review is within the acceptable range." />}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
