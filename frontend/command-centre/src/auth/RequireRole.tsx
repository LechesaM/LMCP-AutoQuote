import { Navigate, useLocation } from "react-router-dom";
import useAuthStore from "./authStore";

export default function RequireRole({ children, permissions = [], roles = [] }) {
  const location = useLocation();
  const hydrated = useAuthStore((state) => state.hydrated);
  const loading = useAuthStore((state) => state.loading);
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const can = useAuthStore((state) => state.can);

  if (!hydrated || loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">Loading session...</div>;
  }

  if (!token || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles.length > 0 && !roles.includes(user.role)) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">You do not have access to this section.</div>;
  }

  if (permissions.length > 0 && !permissions.some((permission) => can(permission))) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">You do not have the required permission.</div>;
  }

  return children;
}

