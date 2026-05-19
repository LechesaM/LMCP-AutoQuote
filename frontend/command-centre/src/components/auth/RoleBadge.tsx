import { ShieldCheck } from "lucide-react";
import { ROLE_LABELS } from "../../auth/roles";

export default function RoleBadge({ role }) {
  const label = ROLE_LABELS[String(role || "").toLowerCase()] || String(role || "unknown");
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-command-cyan/30 bg-command-cyan/10 px-3 py-1 text-xs font-black uppercase tracking-[.18em] text-command-cyan">
      <ShieldCheck size={12} />
      {label}
    </span>
  );
}

