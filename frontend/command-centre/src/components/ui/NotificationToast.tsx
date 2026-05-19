import { Bell, ShieldAlert, ShieldCheck } from "lucide-react";

export default function NotificationToast({ notification }) {
  const tone =
    notification?.severity === "critical"
      ? "border-command-red/30 bg-command-red/10 text-command-red"
      : notification?.severity === "warning"
        ? "border-command-amber/30 bg-command-amber/10 text-command-amber"
        : "border-command-cyan/30 bg-command-cyan/10 text-command-cyan";

  return (
    <div className={`rounded-2xl border p-4 ${tone}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          {notification?.severity === "critical" ? <ShieldAlert size={16} /> : notification?.severity === "warning" ? <ShieldAlert size={16} /> : <ShieldCheck size={16} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] opacity-80">
            <Bell size={12} />
            {notification?.type || "info"}
          </div>
          <div className="mt-2 text-sm font-bold text-white">{notification?.title || "Notification"}</div>
          <div className="mt-1 text-sm text-slate-300">{notification?.message || ""}</div>
        </div>
      </div>
    </div>
  );
}
