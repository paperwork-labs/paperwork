"use client";

import { useUser } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { BackendUser } from "@/types/backend-user";
import { authApi } from "@/services/api";

const QUERY_KEY = ["backend-user", "me"] as const;

export function useBackendUser(): {
  user: BackendUser | null;
  ready: boolean;
  isLoading: boolean;
  error: Error | null;
  refreshMe: () => Promise<void>;
} {
  const { isLoaded, isSignedIn } = useUser();
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => (await authApi.me()) as BackendUser,
    enabled: Boolean(isLoaded && isSignedIn),
    staleTime: 60_000,
    retry: 1,
  });

  const ready =
    isLoaded && (isSignedIn !== true || (!q.isLoading && !q.isFetching));

  return {
    user: (q.data ?? null) as BackendUser | null,
    ready,
    isLoading: q.isLoading,
    error: (q.error as Error) ?? null,
    refreshMe: async () => {
      await qc.invalidateQueries({ queryKey: QUERY_KEY });
    },
  };
}

/** For public pages: no loading gate when signed out; still loads /me when signed in. */
export function useBackendUserOptional(): {
  user: BackendUser | null;
  ready: boolean;
} {
  const { isLoaded, isSignedIn } = useUser();
  const q = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => (await authApi.me()) as BackendUser,
    enabled: Boolean(isLoaded && isSignedIn),
    staleTime: 60_000,
    retry: 1,
  });

  if (!isLoaded) {
    return { user: null, ready: false };
  }
  if (!isSignedIn) {
    return { user: null, ready: true };
  }
  return {
    user: (q.data ?? null) as BackendUser | null,
    ready: !q.isLoading && !q.isFetching,
  };
}
