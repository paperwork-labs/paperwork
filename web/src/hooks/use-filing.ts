"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse } from "@/types";

interface FilingData {
  id: string;
  user_id: string;
  tax_year: number;
  filing_status_type: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
}

export function useFiling(filingId: string | null) {
  return useQuery({
    queryKey: ["filing", filingId],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<FilingData>>(
        `/api/v1/filings/${filingId}`
      );
      return data.data!;
    },
    enabled: !!filingId,
  });
}

export function useCreateFiling() {
  const { csrfToken } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (taxYear: number = 2025) => {
      const res = await api.post<ApiResponse<FilingData>>(
        "/api/v1/filings",
        { tax_year: taxYear },
        { headers: { "X-CSRF-Token": csrfToken ?? "" } }
      );
      return res.data.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["filings"] });
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useUpdateFiling() {
  const { csrfToken } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      filingId,
      ...data
    }: {
      filingId: string;
      filing_status_type?: string;
      status?: string;
    }) => {
      const res = await api.patch<ApiResponse<FilingData>>(
        `/api/v1/filings/${filingId}`,
        data,
        { headers: { "X-CSRF-Token": csrfToken ?? "" } }
      );
      return res.data.data!;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["filing", data.id], data);
      queryClient.invalidateQueries({ queryKey: ["filings"] });
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useConfirmData() {
  const { csrfToken } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (filingId: string) => {
      const res = await api.post<ApiResponse<FilingData>>(
        `/api/v1/filings/${filingId}/confirm`,
        {},
        { headers: { "X-CSRF-Token": csrfToken ?? "" } }
      );
      return res.data.data!;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["filing", data.id], data);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}
