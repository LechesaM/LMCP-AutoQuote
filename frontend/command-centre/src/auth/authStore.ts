import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { fetchCurrentPermissions, fetchCurrentUser, loginWithCredentials, logoutSession } from "./authClient";
import { AUTH_STORAGE_KEY } from "./authConstants";

const initialState = {
  hydrated: false,
  loading: true,
  token: "",
  user: null,
  permissions: [],
  error: "",
};

const useAuthStore = create(
  persist(
    (set, get) => ({
      ...initialState,
      can: (permission) => (get().permissions || []).includes(permission),
      bootstrap: async () => {
        const token = get().token;
        if (!token) {
          set({ hydrated: true, loading: false });
          return null;
        }
        try {
          const session = await fetchCurrentUser();
          const permissions = session?.permissions || [];
          set({
            hydrated: true,
            loading: false,
            error: "",
            token,
            permissions,
            user: session?.user || null,
          });
          return session;
        } catch (error) {
          set({ ...initialState, hydrated: true, loading: false });
          return null;
        }
      },
      login: async (email, password) => {
        set({ loading: true, error: "" });
        try {
          const session = await loginWithCredentials(email, password);
          set({
            hydrated: true,
            loading: false,
            error: "",
            token: session?.access_token || "",
            user: session?.user || null,
            permissions: session?.permissions || [],
          });
          return session;
        } catch (error) {
          set({ loading: false, error: error instanceof Error ? error.message : "Login failed" });
          throw error;
        }
      },
      refreshPermissions: async () => {
        const session = await fetchCurrentPermissions();
        set((state) => ({
          ...state,
          permissions: session?.permissions || [],
          user: state.user ? { ...state.user, role: session?.role || state.user.role } : state.user,
        }));
        return session;
      },
      logout: async () => {
        try {
          await logoutSession();
        } catch (error) {
          // ignore logout transport failures and clear local session anyway
        }
        set({ ...initialState, hydrated: true, loading: false });
      },
      setSession: (session) => {
        set({
          hydrated: true,
          loading: false,
          error: "",
          token: session?.access_token || session?.token || "",
          user: session?.user || null,
          permissions: session?.permissions || [],
        });
      },
    }),
    {
      name: AUTH_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ token: state.token, user: state.user, permissions: state.permissions }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.hydrated = true;
          state.loading = false;
        }
      },
    },
  ),
);

export default useAuthStore;
