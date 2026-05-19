import { PackageSearch } from "lucide-react";

type EmptyTelemetryStateProps = {
  title: string;
  description?: string;
};

export default function EmptyTelemetryState({ title, description = "" }: EmptyTelemetryStateProps) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-700/70 bg-slate-950/30 p-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-700/60 bg-slate-950/55 text-slate-400">
        <PackageSearch size={20} />
      </div>
      <div className="mt-4 text-base font-black text-white">{title}</div>
      {description ? <p className="mt-2 text-sm text-slate-400">{description}</p> : null}
    </div>
  );
}
