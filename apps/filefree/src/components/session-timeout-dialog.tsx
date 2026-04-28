"use client";

import { useAuth } from "@clerk/nextjs";
import { SessionTimeoutDialog as AuthSessionTimeoutDialog } from "@paperwork-labs/auth-clerk";
import { useLogout } from "@/hooks/use-auth";

export function SessionTimeoutDialog() {
  const { isSignedIn } = useAuth();
  const logout = useLogout();

  return (
    <AuthSessionTimeoutDialog
      isAuthenticated={Boolean(isSignedIn)}
      onLogout={() => logout.mutate()}
    />
  );
}
