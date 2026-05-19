import { type ReactNode } from "react";

type TelemetryStatProps = {
  label: string;
  value: ReactNode;
  description?: string;
  tone?: "slate" | "green" | "cyan" | "amber" | "red";
};

export default function TelemetryStat({ label, value, description = "", tone = "slate" }: TelemetryStatProps) {
  const palette =
    tone === "green"
      ? "border-command-green/30 bg-command-green/10 text-command-green"
      : tone === "cyan"
        ? "border-command-cyan/30 bg-command-cyan/10 text-command-cyan"
        : tone === "amber"
          ? "border-command-amber/30 bg-command-amber/10 text-command-amber"
          : tone === "red"
            ? "border-command-red/30 bg-command-red/10 text-command-red"
            : "border-slate-700/60 bg-slate-950/45 text-slate-300";

  return (
    <div className={`rounded-2xl border p-4 ${palette}`}>
      <div className="text-[10px] font-black uppercase tracking-[.24em] opacity-85">{label}</div>
      <div className="mt-2 text-3xl font-black text-white">{value}</div>
      {description ? <div className="mt-1 text-xs text-slate-400">{description}</div> : null}
    </div>
  );
}
