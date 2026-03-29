/**
 * Formation Wizard Store
 *
 * Zustand store for managing formation wizard state.
 * Persists to localStorage for recovery across page refreshes.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type WizardStep =
  | "state"
  | "name"
  | "details"
  | "agent"
  | "address"
  | "members"
  | "review";

export const WIZARD_STEPS: WizardStep[] = [
  "state",
  "name",
  "details",
  "agent",
  "address",
  "members",
  "review",
];

export interface Address {
  street1: string;
  street2?: string;
  city: string;
  state: string;
  zip: string;
}

export interface Member {
  id: string;
  name: string;
  address: Address;
  role: "member" | "manager" | "organizer";
  ownershipPercentage?: number;
  isOrganizer: boolean;
}

export interface RegisteredAgent {
  type: "self" | "launchfree" | "other";
  name: string;
  address: Address;
  isCommercial: boolean;
}

export interface FormationData {
  stateCode: string;
  businessName: string;
  nameSuffix: "LLC" | "L.L.C." | "Limited Liability Company";
  businessPurpose: string;
  managementType: "member" | "manager";
  registeredAgent: RegisteredAgent;
  principalAddress: Address;
  mailingAddress?: Address;
  sameMailingAddress: boolean;
  members: Member[];
  effectiveDate?: string;
}

export interface FormationStore {
  currentStep: WizardStep;
  data: Partial<FormationData>;
  isSubmitting: boolean;
  submissionError: string | null;

  setStep: (step: WizardStep) => void;
  nextStep: () => void;
  prevStep: () => void;
  updateData: (partial: Partial<FormationData>) => void;
  setSubmitting: (isSubmitting: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
  canProceed: (step: WizardStep) => boolean;
}

const initialData: Partial<FormationData> = {
  nameSuffix: "LLC",
  businessPurpose: "Any lawful purpose",
  managementType: "member",
  sameMailingAddress: true,
  members: [],
  registeredAgent: {
    type: "launchfree",
    name: "",
    address: { street1: "", city: "", state: "", zip: "" },
    isCommercial: false,
  },
};

export const useFormationStore = create<FormationStore>()(
  persist(
    (set, get) => ({
      currentStep: "state",
      data: initialData,
      isSubmitting: false,
      submissionError: null,

      setStep: (step) => set({ currentStep: step }),

      nextStep: () => {
        const { currentStep } = get();
        const currentIndex = WIZARD_STEPS.indexOf(currentStep);
        if (currentIndex < WIZARD_STEPS.length - 1) {
          set({ currentStep: WIZARD_STEPS[currentIndex + 1] });
        }
      },

      prevStep: () => {
        const { currentStep } = get();
        const currentIndex = WIZARD_STEPS.indexOf(currentStep);
        if (currentIndex > 0) {
          set({ currentStep: WIZARD_STEPS[currentIndex - 1] });
        }
      },

      updateData: (partial) =>
        set((state) => ({
          data: { ...state.data, ...partial },
        })),

      setSubmitting: (isSubmitting) => set({ isSubmitting }),

      setError: (error) => set({ submissionError: error }),

      reset: () =>
        set({
          currentStep: "state",
          data: initialData,
          isSubmitting: false,
          submissionError: null,
        }),

      canProceed: (step) => {
        const { data } = get();
        switch (step) {
          case "state":
            return Boolean(data.stateCode);
          case "name":
            return Boolean(data.businessName && data.businessName.length >= 2);
          case "details":
            return Boolean(data.businessPurpose && data.managementType);
          case "agent":
            return Boolean(
              data.registeredAgent?.type &&
                (data.registeredAgent.type === "launchfree" ||
                  (data.registeredAgent.name && data.registeredAgent.address.street1))
            );
          case "address":
            return Boolean(
              data.principalAddress?.street1 &&
                data.principalAddress?.city &&
                data.principalAddress?.state &&
                data.principalAddress?.zip
            );
          case "members":
            return Boolean(data.members && data.members.length > 0);
          case "review":
            return true;
          default:
            return false;
        }
      },
    }),
    {
      name: "launchfree-formation",
      partialize: (state) => ({
        currentStep: state.currentStep,
        data: state.data,
      }),
    }
  )
);
