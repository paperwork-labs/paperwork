"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse } from "@/types";

export interface TaxCalculationData {
  adjusted_gross_income: number;
  standard_deduction: number;
  taxable_income: number;
  federal_tax: number;
  state_tax: number;
  total_withheld: number;
  refund_amount: number;
  owed_amount: number;
  ai_insights?: Record<string, unknown>;
  calculated_at: string;
}

export function useCalculation(filingId: string | null) {
  return useQuery({
    queryKey: ["calculation", filingId],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<TaxCalculationData>>(
        `/api/v1/tax/calculation/${filingId}`
      );
      return data.data!;
    },
    enabled: !!filingId,
    retry: false,
  });
}

export function useCalculateTax() {
  const { csrfToken } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (filingId: string) => {
      const res = await api.post<ApiResponse<TaxCalculationData>>(
        `/api/v1/tax/calculate/${filingId}`,
        {},
        { headers: { "X-CSRF-Token": csrfToken ?? "" } }
      );
      return res.data.data!;
    },
    onSuccess: (data, filingId) => {
      queryClient.setQueryData(["calculation", filingId], data);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}
