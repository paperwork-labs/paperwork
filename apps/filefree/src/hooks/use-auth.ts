"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse, User } from "@/types";

interface AuthResponseData {
  user: User;
  csrf_token: string;
}

function safeRedirect(raw: string | null, fallback: string): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//")) return fallback;
  try {
    const url = new URL(raw, "http://localhost");
    if (url.protocol !== "http:" && url.protocol !== "https:") return fallback;
  } catch {
    return fallback;
  }
  return raw;
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
      router.push(safeRedirect(searchParams.get("redirect"), "/file"));
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
      router.push(safeRedirect(searchParams.get("redirect"), "/file"));
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useGoogleAuth() {
  const { setUser } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (idToken: string) => {
      const res = await api.post<ApiResponse<AuthResponseData>>(
        "/api/v1/auth/google",
        { id_token: idToken }
      );
      return res.data.data!;
    },
    onSuccess: ({ user, csrf_token }) => {
      setUser(user, csrf_token);
      queryClient.setQueryData(["auth", "me"], user);
      toast.success("Welcome to FileFree!");
      router.push(safeRedirect(searchParams.get("redirect"), "/file"));
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });
}

export function useAppleAuth() {
  const { setUser } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { idToken: string; user?: unknown }) => {
      const res = await api.post<ApiResponse<AuthResponseData>>(
        "/api/v1/auth/apple",
        { id_token: data.idToken, user: data.user }
      );
      return res.data.data!;
    },
    onSuccess: ({ user, csrf_token }) => {
      setUser(user, csrf_token);
      queryClient.setQueryData(["auth", "me"], user);
      toast.success("Welcome to FileFree!");
      router.push(safeRedirect(searchParams.get("redirect"), "/file"));
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
      const headers: Record<string, string> = {};
      if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
      await api.post("/api/v1/auth/logout", null, { headers });
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
      const headers: Record<string, string> = {};
      if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
      await api.delete("/api/v1/auth/account", { headers });
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
