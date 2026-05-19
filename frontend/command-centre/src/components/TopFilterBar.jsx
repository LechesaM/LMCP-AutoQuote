import { Download, SlidersHorizontal, Zap } from "lucide-react";
import { filters } from "../data/harvestedRfqs";
import StateBadge from "./ui/StateBadge.tsx";
import { SkeletonCard } from "./ui/SkeletonBlocks.tsx";

function SelectBox({ label, value }) {
  return (
    <div className="min-w-[160px] rounded-2xl border border-slate-700/70 bg-slate-950/50 px-4 py-3">
      <div className="text-[10px] font-bold uppercase tracking-[.24em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

export default function TopFilterBar({ state = "ready" }) {
  if (state === "loading") {
    return (
      <div className="glass-card rounded-3xl p-4">
        <SkeletonCard lines={2} />
      </div>
    );
  }

  const isEmpty = state === "empty";

  return (
    <div className={`glass-card flex flex-wrap items-center justify-between gap-4 rounded-3xl p-4 ${state === "stale" ? "opacity-85" : ""}`}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="mr-1 flex h-11 w-11 items-center justify-center rounded-2xl bg-command-green/15 text-command-green">
          <SlidersHorizontal size={20} />
        </div>
        <SelectBox label="Time Period" value={isEmpty ? "—" : filters.timePeriod} />
        <SelectBox label="Tender Type" value={isEmpty ? "—" : filters.tenderType} />
        <SelectBox label="Profit Threshold" value={isEmpty ? "—" : filters.profitThreshold} />
        <SelectBox label="Province" value={isEmpty ? "—" : filters.province} />
        <SelectBox label="Radar Mode" value={isEmpty ? "—" : filters.radarMode} />
      </div>
      <div className="flex items-center gap-3">
        <StateBadge state={state === "refreshing" ? "refreshing" : state === "stale" ? "stale" : state === "error" ? "error" : "ready"} />
        <button className="flex items-center gap-2 rounded-2xl bg-command-green px-5 py-3 text-sm font-bold text-slate-950 shadow-glow">
          <Zap size={17} />
          Apply Filters
        </button>
        <button className="flex items-center gap-2 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-5 py-3 text-sm font-bold text-command-cyan">
          <Download size={17} />
          Export Report
        </button>
      </div>
    </div>
  );
}
