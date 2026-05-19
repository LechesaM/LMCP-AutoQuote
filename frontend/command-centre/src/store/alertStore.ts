import { create } from "zustand";
import { recentAlerts } from "../data/harvestedRfqs";

const useAlertStore = create((set, get) => ({
  items: recentAlerts,
  severity: "advisory",
  refreshAlerts: () => set({ items: recentAlerts, severity: "advisory" }),
  getAlertSnapshot: () => ({
    items: get().items,
    severity: get().severity,
  }),
}));

export default useAlertStore;
