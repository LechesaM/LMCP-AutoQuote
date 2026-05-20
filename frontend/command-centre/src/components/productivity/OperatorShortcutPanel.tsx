import SectionPanel from "../ui/SectionPanel.tsx";

export default function OperatorShortcutPanel({ shortcuts }) {
  return (
    <SectionPanel title="Operator Shortcuts" description="Keyboard and quick-filter reference." state={shortcuts?.status || "ready"}>
      <div className="grid gap-3 md:grid-cols-2">
        {(shortcuts?.shortcuts || []).map((shortcut) => (
          <div key={`${shortcut.label}-${shortcut.key}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-black text-white">{shortcut.label}</div>
              <div className="rounded-full border border-command-cyan/40 bg-command-cyan/10 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-command-cyan">{shortcut.key}</div>
            </div>
            <div className="mt-2 text-sm text-slate-400">{shortcut.action}</div>
          </div>
        ))}
      </div>
    </SectionPanel>
  );
}

