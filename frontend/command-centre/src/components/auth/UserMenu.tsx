import { LogOut, UserCircle2 } from "lucide-react";
import useAuthStore from "../../auth/authStore";
import RoleBadge from "./RoleBadge.tsx";

export default function UserMenu() {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  if (!user) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-2">
      <div className="flex items-center gap-2">
        <UserCircle2 size={18} className="text-command-cyan" />
        <div>
          <div className="text-sm font-bold text-white">{user.display_name || user.email}</div>
          <div className="text-xs text-slate-400">{user.email}</div>
        </div>
      </div>
      <RoleBadge role={user.role} />
      <button
        className="inline-flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-950/60 px-3 py-2 text-xs font-black uppercase tracking-[.18em] text-slate-300 transition hover:border-command-cyan/40 hover:text-white"
        onClick={() => logout()}
        type="button"
      >
        <LogOut size={12} />
        Logout
      </button>
    </div>
  );
}

