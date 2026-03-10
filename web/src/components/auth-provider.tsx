"use client";

import { useEffect } from "react";
import api from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse, User } from "@/types";

interface MeResponseData {
  user: User;
  csrf_token?: string;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser, clearAuth, setLoading } = useAuthStore();

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      try {
        const { data } = await api.get<ApiResponse<MeResponseData>>(
          "/api/v1/auth/me"
        );
        if (!cancelled && data.data?.user) {
          setUser(data.data.user, data.data.csrf_token);
        }
      } catch {
        if (!cancelled) {
          clearAuth();
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSession();
    return () => {
      cancelled = true;
    };
  }, [setUser, clearAuth, setLoading]);

  return <>{children}</>;
}
