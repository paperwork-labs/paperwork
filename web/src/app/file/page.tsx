"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useCreateFiling } from "@/hooks/use-filing";
import { useFilingStore } from "@/stores/filing-store";

export default function FilePage() {
  const router = useRouter();
  const createFiling = useCreateFiling();
  const { filingId, setFilingId, setCurrentStep, reset } = useFilingStore();

  useEffect(() => {
    if (filingId) {
      router.replace("/file/w2");
      return;
    }

    reset();
    createFiling.mutate(2025, {
      onSuccess: (data) => {
        setFilingId(data.id);
        setCurrentStep(0);
        router.replace("/file/w2");
      },
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        <p className="text-sm text-muted-foreground">
          Setting up your tax return...
        </p>
      </div>
    </div>
  );
}
