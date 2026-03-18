import { create } from "zustand";

export interface W2Data {
  employer_name: string;
  employer_ein: string;
  employer_address: string;
  employee_name: string;
  employee_address: string;
  ssn_last_four: string;
  wages: number;
  federal_tax_withheld: number;
  social_security_wages: number;
  social_security_tax: number;
  medicare_wages: number;
  medicare_tax: number;
  state: string;
  state_wages: number;
  state_tax_withheld: number;
  confidence?: number;
}

export const FILING_STEPS = [
  { key: "w2", label: "W-2", path: "/file/w2" },
  { key: "confirm", label: "Confirm", path: "/file/confirm" },
  { key: "details", label: "Details", path: "/file/details" },
  { key: "summary", label: "Summary", path: "/file/summary" },
] as const;

export type StepKey = (typeof FILING_STEPS)[number]["key"];

interface FilingState {
  filingId: string | null;
  taxYear: number;
  currentStep: number;
  w2s: W2Data[];
  filingStatusType: string | null;

  setFilingId: (id: string) => void;
  setCurrentStep: (step: number) => void;
  addW2: (w2: W2Data) => void;
  updateW2: (index: number, w2: Partial<W2Data>) => void;
  removeW2: (index: number) => void;
  setFilingStatusType: (type: string) => void;
  reset: () => void;
}

const INITIAL_STATE = {
  filingId: null,
  taxYear: 2025,
  currentStep: 0,
  w2s: [] as W2Data[],
  filingStatusType: null,
};

export const useFilingStore = create<FilingState>((set) => ({
  ...INITIAL_STATE,

  setFilingId: (id) => set({ filingId: id }),
  setCurrentStep: (step) => set({ currentStep: step }),
  addW2: (w2) => set((state) => ({ w2s: [...state.w2s, w2] })),
  updateW2: (index, updates) =>
    set((state) => ({
      w2s: state.w2s.map((w2, i) =>
        i === index ? { ...w2, ...updates } : w2
      ),
    })),
  removeW2: (index) =>
    set((state) => ({
      w2s: state.w2s.filter((_, i) => i !== index),
    })),
  setFilingStatusType: (type) => set({ filingStatusType: type }),
  reset: () => set(INITIAL_STATE),
}));
