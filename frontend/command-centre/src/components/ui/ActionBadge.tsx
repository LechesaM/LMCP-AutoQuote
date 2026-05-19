export default function ActionBadge({ action, tone = "amber" }) {
  const palette =
    tone === "red"
      ? "border-command-red/40 bg-command-red/10 text-command-red"
      : tone === "green"
        ? "border-command-green/40 bg-command-green/10 text-command-green"
        : tone === "cyan"
          ? "border-command-cyan/40 bg-command-cyan/10 text-command-cyan"
          : "border-command-amber/40 bg-command-amber/10 text-command-amber";

  return <span className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] ${palette}`}>{action}</span>;
}
