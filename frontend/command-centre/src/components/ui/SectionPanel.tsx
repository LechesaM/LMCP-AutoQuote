import { type ReactNode } from "react";
import StateBadge from "./StateBadge.tsx";

type SectionPanelProps = {
  title: string;
  description?: string;
  children: ReactNode;
  state?: "ready" | "loading" | "error" | "empty" | "stale" | "refreshing";
  actions?: ReactNode;
};

export default function SectionPanel({ title, description, children, state = "ready", actions }: SectionPanelProps) {
  return (
    <section className="glass-card rounded-3xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-black text-white">{title}</h3>
          {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          {state !== "ready" ? <StateBadge state={state} /> : null}
          {actions}
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}
