import Pill from "../components/shared/Pill";
import SectionCard from "../components/shared/SectionCard";
import StatCard from "../components/shared/StatCard";

export default function DashboardPage({ summary, tenders, alerts }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Harvested Today" value={summary.harvestedToday} note="Fresh opportunities detected today" />
        <StatCard title="Qualified Opportunities" value={summary.qualified} note="Matched to LMCP filters" />
        <StatCard title="Quote Ready" value={summary.quoteReady} note="Ready for pricing and packaging" />
        <StatCard title="Submitted" value={summary.submitted} note="Already sent to buyers" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <SectionCard title="Closing Soon" subtitle="High-priority opportunities requiring immediate attention" right={<Pill tone="amber">Urgent</Pill>}>
          <div className="space-y-3">
            {tenders.slice(0, 3).map((item) => (
              <div key={item.id} className="rounded-2xl bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-slate-900">{item.title}</div>
                    <div className="mt-1 text-sm text-slate-500">
                      {item.buyer} • {item.province}
                    </div>
                  </div>
                  <Pill tone="green">{item.score}</Pill>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Pill tone="blue">{item.submission_type}</Pill>
                  <Pill>{item.close_date}</Pill>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="System Alerts" subtitle="Operational intelligence from the live stack">
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div key={alert} className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                {alert}
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Executive Snapshot" subtitle="What leadership sees at a glance">
          <div className="grid gap-3">
            <div className="rounded-2xl bg-slate-50 p-4">
              <div className="text-sm text-slate-500">Best winning zone</div>
              <div className="mt-1 text-lg font-semibold">Free State infrastructure and maintenance opportunities</div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <div className="text-sm text-slate-500">Buyer activity</div>
              <div className="mt-1 text-lg font-semibold">DPWI and public works entities leading release volume</div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4">
              <div className="text-sm text-slate-500">Submission focus</div>
              <div className="mt-1 text-lg font-semibold">Email-only and portal-only opportunities prioritised</div>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
