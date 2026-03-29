"use client";

import { useFormationStore, type WizardStep } from "@/lib/stores/formation";
import { StateStep } from "@/components/formation/state-step";
import { NameStep } from "@/components/formation/name-step";
import { DetailsStep } from "@/components/formation/details-step";
import { AgentStep } from "@/components/formation/agent-step";
import { AddressStep } from "@/components/formation/address-step";
import { MembersStep } from "@/components/formation/members-step";
import { ReviewStep } from "@/components/formation/review-step";
import { AnimatePresence, motion } from "framer-motion";

const STEP_COMPONENTS: Record<WizardStep, React.ComponentType> = {
  state: StateStep,
  name: NameStep,
  details: DetailsStep,
  agent: AgentStep,
  address: AddressStep,
  members: MembersStep,
  review: ReviewStep,
};

export default function FormationWizardPage() {
  const { currentStep } = useFormationStore();
  const StepComponent = STEP_COMPONENTS[currentStep];

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={currentStep}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{ duration: 0.2 }}
      >
        <StepComponent />
      </motion.div>
    </AnimatePresence>
  );
}
