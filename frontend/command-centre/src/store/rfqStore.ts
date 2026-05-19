import { create } from "zustand";
import { rfqRules } from "../utils/tenderFilters";

const useRfqStore = create((set, get) => ({
  rfqRules,
  selectedRfqId: null,
  qualificationSummary: {
    manualGovernanceOnly: true,
    reviewReadyRequired: true,
    proofCaptureRequired: true,
  },
  selectRfq: (rfqId) => set({ selectedRfqId: rfqId }),
  refreshQualificationSummary: () =>
    set({
      qualificationSummary: {
        manualGovernanceOnly: true,
        reviewReadyRequired: true,
        proofCaptureRequired: true,
      },
    }),
  getRfqSnapshot: () => ({
    rfqRules: get().rfqRules,
    selectedRfqId: get().selectedRfqId,
    qualificationSummary: get().qualificationSummary,
  }),
}));

export default useRfqStore;
