import { commandMetrics, provinceDistribution } from "../data/harvestedRfqs";
import StateBadge from "./ui/StateBadge.tsx";
import { SkeletonCard } from "./ui/SkeletonBlocks.tsx";

const dots = [
  ["Gauteng", "left-[57%] top-[30%]"],
  ["Western Cape", "left-[28%] top-[68%]"],
  ["KZN", "left-[70%] top-[61%]"],
  ["Limpopo", "left-[52%] top-[14%]"],
  ["Mpumalanga", "left-[72%] top-[36%]"],
  ["Eastern Cape", "left-[55%] top-[76%]"],
  ["Free State", "left-[45%] top-[52%]"],
  ["North West", "left-[35%] top-[35%]"],
  ["Northern Cape", "left-[22%] top-[48%]"],
];

function strength(name) {
  const province = provinceDistribution.find((row) => row.province === name);
  return province ? Math.max(8, Math.round(province.eligible / 8)) : 8;
}

export default function OpportunityRadar({ state = "ready", onRetry }) {
  if (state === "loading") {
    return (
      <div className="glass-card rounded-3xl p-6">
        <SkeletonCard lines={5} />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="glass-card rounded-3xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-black text-white">Opportunity Radar</h3>
            <p className="text-sm text-slate-400">Unable to load telemetry.</p>
          </div>
          <StateBadge state="error" />
        </div>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const metrics = state === "empty" ? { totalHarvested: 0, eligibleRfqs: 0, eligibleRate: 0 } : commandMetrics;

  return (
    <div className={`glass-card rounded-3xl p-6 ${state === "stale" ? "opacity-85" : ""}`}>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-black text-white">Opportunity Radar</h3>
          <p className="text-sm text-slate-400">Province signal density and active RFQ telemetry.</p>
        </div>
        <StateBadge state={state === "refreshing" ? "refreshing" : state === "stale" ? "stale" : "ready"} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_150px]">
        <div className="relative mx-auto h-[330px] w-[330px] rounded-full border border-command-green/35 bg-slate-950/80 shadow-glow">
          <div className="absolute inset-4 rounded-full border border-command-green/20" />
          <div className="absolute inset-12 rounded-full border border-command-green/25" />
          <div className="absolute inset-20 rounded-full border border-command-green/30" />
          <div className="absolute left-1/2 top-0 h-full w-px bg-command-green/20" />
          <div className="absolute left-0 top-1/2 h-px w-full bg-command-green/20" />
          <div className="radar-sweep absolute inset-0 rounded-full opacity-80 animate-radarSweep" />
          <div className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-command-green shadow-glow" />
          {dots.map(([name, position]) => (
            <div
              key={name}
              className={`absolute ${position} animate-glowPulse rounded-full bg-command-green shadow-glow`}
              style={{ width: `${strength(name)}px`, height: `${strength(name)}px` }}
              title={name}
            />
          ))}
        </div>

        <div className="space-y-3">
          {[
            ["Sources", metrics.totalHarvested, "slate"],
            ["Eligible", metrics.eligibleRfqs, "green"],
            ["Eligible Rate", `${metrics.eligibleRate}%`, "cyan"],
          ].map(([label, value, tone]) => (
            <div
              key={label}
              className={`rounded-2xl border ${
                tone === "green"
                  ? "border-command-green/30 bg-command-green/10"
                  : tone === "cyan"
                    ? "border-command-cyan/30 bg-command-cyan/10"
                    : "border-slate-700/70 bg-slate-950/55"
              } p-4`}
            >
              <div
                className={`text-[10px] font-black uppercase tracking-[.24em] ${
                  tone === "green" ? "text-command-green" : tone === "cyan" ? "text-command-cyan" : "text-slate-500"
                }`}
              >
                {label}
              </div>
              <div className="mt-2 text-2xl font-black text-white">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
