"use client";

import * as React from "react";
import { useAuth } from "@clerk/nextjs";

import { setClerkApiTokenGetter } from "@/lib/clerk-api-token";

/**
 * Registers Clerk `getToken` for axios + GDPR client interceptors.
 */
export function ClerkTokenBridge() {
  const { getToken, isLoaded } = useAuth();

  React.useEffect(() => {
    if (!isLoaded) {
      setClerkApiTokenGetter(null);
      return;
    }
    setClerkApiTokenGetter(() => getToken());
    return () => setClerkApiTokenGetter(null);
  }, [getToken, isLoaded]);

  return null;
}
