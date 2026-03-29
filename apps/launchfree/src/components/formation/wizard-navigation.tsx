"use client";

import { useFormationStore, WIZARD_STEPS } from "@/lib/stores/formation";
import { Button } from "@paperwork-labs/ui";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";

interface WizardNavigationProps {
  onNext?: () => void | Promise<void>;
  nextLabel?: string;
  showBack?: boolean;
  isLoading?: boolean;
  disabled?: boolean;
}

export function WizardNavigation({
  onNext,
  nextLabel = "Continue",
  showBack = true,
  isLoading = false,
  disabled = false,
}: WizardNavigationProps) {
  const { currentStep, nextStep, prevStep, canProceed } = useFormationStore();
  const currentIndex = WIZARD_STEPS.indexOf(currentStep);
  const isFirstStep = currentIndex === 0;
  const isLastStep = currentIndex === WIZARD_STEPS.length - 1;
  const canContinue = canProceed(currentStep) && !disabled;

  const handleNext = async () => {
    if (onNext) {
      await onNext();
    } else {
      nextStep();
    }
  };

  return (
    <div className="mt-8 flex items-center justify-between">
      {showBack && !isFirstStep ? (
        <Button
          type="button"
          variant="ghost"
          onClick={prevStep}
          className="text-slate-400 hover:text-white"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
      ) : (
        <div />
      )}

      <Button
        type="button"
        onClick={handleNext}
        disabled={!canContinue || isLoading}
        className="bg-gradient-to-r from-teal-400 to-cyan-500 text-slate-950 hover:from-teal-300 hover:to-cyan-400"
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : (
          <>
            {isLastStep ? "Submit" : nextLabel}
            {!isLastStep && <ArrowRight className="ml-2 h-4 w-4" />}
          </>
        )}
      </Button>
    </div>
  );
}
