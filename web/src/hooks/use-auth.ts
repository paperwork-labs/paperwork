"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse, User } from "@/types";

interface AuthResponseData {
  user: User;
  csrf_token: string;
}

interface MeResponseData {
  user: User;
}

export function useCurrentUser() {
  const { setUser, clearAuth, setLoading } = useAuthStore();

  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<MeResponseData>>("/api/v1/auth/me");
      return data.data!.user;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
    meta: {
      onSuccess: (user: User) => {
        setUser(user);
      },
      onError: () => {
        clearAuth();
      },
      onSettled: () => {
        setLoading(false);
      },
    },
  });
}

export function useRegister() {
  const { setUser } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      email: string;
      password: string;
      full_name: string;
    }) => {
      const res = await api.post<ApiResponse<AuthResponseData>>(
        "/api/v1/auth/register",
        data
      );
      return res.data.data!;
    },
    onSuccess: ({ user, csrf_token }) => {
      setUser(user, csrf_token);
      queryClient.setQueryData(["auth", "me"], user);
      toast.success("Welcome to FileFree!");
      router.push(searchParams.get("redirect") || "/file");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useLogin() {
  const { setUser } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { email: string; password: string }) => {
      const res = await api.post<ApiResponse<AuthResponseData>>(
        "/api/v1/auth/login",
        data
      );
      return res.data.data!;
    },
    onSuccess: ({ user, csrf_token }) => {
      setUser(user, csrf_token);
      queryClient.setQueryData(["auth", "me"], user);
      toast.success("Welcome back!");
      router.push(searchParams.get("redirect") || "/file");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useLogout() {
  const { csrfToken, clearAuth } = useAuthStore();
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await api.post("/api/v1/auth/logout", null, {
        headers: { "X-CSRF-Token": csrfToken ?? "" },
      });
    },
    onSuccess: () => {
      clearAuth();
      queryClient.removeQueries({ queryKey: ["auth"] });
      router.push("/");
    },
    onError: (error: Error) => {
      toast.error(error.message);
      clearAuth();
      router.push("/");
    },
  });
}

export function useDeleteAccount() {
  const { csrfToken, clearAuth } = useAuthStore();
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await api.delete("/api/v1/auth/account", {
        headers: { "X-CSRF-Token": csrfToken ?? "" },
      });
    },
    onSuccess: () => {
      clearAuth();
      queryClient.removeQueries({ queryKey: ["auth"] });
      toast.success("Your account and all data have been deleted.");
      router.push("/");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}
