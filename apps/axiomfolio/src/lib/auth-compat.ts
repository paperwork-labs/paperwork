"use client";

import { useUser } from "@clerk/nextjs";

import { useAuth } from "@/context/AuthContext";
import type { User } from "@/context/AuthContext";

export type AuthCompatUser = {
  /** Stable id: Clerk user id or legacy user id as string */
  id: string;
  email: string | null;
  username: string | null;
  fullName: string | null;
  imageUrl: string | null;
  /** Backend user when the session is legacy `qm_token` */
  legacyUser: User | null;
  /** Clerk user id when the session is Clerk */
  clerkUserId: string | null;
};

export type UseAuthCompatResult = {
  user: AuthCompatUser | null;
  isAuthenticated: boolean;
  isLoaded: boolean;
};

/**
 * Dual-mode auth: Clerk session wins; otherwise legacy `qm_token` + AuthContext.
 * Use for UI that should treat either session as “signed in” during WS-14 migration.
 */
export function useAuthCompat(): UseAuthCompatResult {
  const { isLoaded: clerkLoaded, isSignedIn, user: clerkUser } = useUser();
  const { user: legacyUser, token, ready: legacyReady } = useAuth();

  const legacySession = legacyReady && !!token;
  const isLoaded = clerkLoaded && (isSignedIn === true || legacyReady);
  const isAuthenticated = Boolean(isSignedIn || legacySession);

  let user: AuthCompatUser | null = null;
  if (isSignedIn && clerkUser) {
    user = {
      id: clerkUser.id,
      email: clerkUser.primaryEmailAddress?.emailAddress ?? null,
      username:
        clerkUser.username ??
        clerkUser.primaryEmailAddress?.emailAddress?.split("@")[0] ??
        null,
      fullName: clerkUser.fullName || null,
      imageUrl: clerkUser.imageUrl,
      legacyUser: null,
      clerkUserId: clerkUser.id,
    };
  } else if (legacySession && legacyUser) {
    user = {
      id: String(legacyUser.id),
      email: legacyUser.email,
      username: legacyUser.username,
      fullName: legacyUser.full_name ?? null,
      imageUrl: null,
      legacyUser,
      clerkUserId: null,
    };
  }

  return { user, isAuthenticated, isLoaded };
}
