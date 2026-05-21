import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useAuthStore from "../../auth/authStore";

export default function LoginForm() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);
  const [email, setEmail] = useState("operator@lmcp.local");
  const [password, setPassword] = useState("operator");
  const [localError, setLocalError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setLocalError("");
    try {
      await login(email, password);
      navigate("/review", { replace: true });
    } catch (exception) {
      setLocalError(exception instanceof Error ? exception.message : "Login failed");
    }
  };

  const message = localError || error;

  return (
    <form className="space-y-4 rounded-3xl border border-slate-700/60 bg-slate-950/55 p-6 shadow-2xl shadow-black/20" onSubmit={submit}>
      <div>
        <label className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Email</label>
        <input
          className="mt-2 w-full rounded-2xl border border-slate-700/60 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="operator@lmcp.local"
          type="email"
          value={email}
        />
      </div>
      <div>
        <label className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Password</label>
        <input
          className="mt-2 w-full rounded-2xl border border-slate-700/60 bg-slate-950/60 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500"
          onChange={(event) => setPassword(event.target.value)}
          placeholder="password"
          type="password"
          value={password}
        />
      </div>
      {message ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{message}</div> : null}
      <button
        className="w-full rounded-2xl border border-command-cyan/40 bg-command-cyan/15 px-4 py-3 text-sm font-black uppercase tracking-[.22em] text-command-cyan transition hover:bg-command-cyan/20 disabled:opacity-60"
        disabled={loading}
        type="submit"
      >
        {loading ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
