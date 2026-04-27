"use client";

import { SessionTimeoutDialog as AuthSessionTimeoutDialog } from "@paperwork-labs/auth-clerk";
import { useLogout } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";

export function SessionTimeoutDialog() {
  const { isAuthenticated } = useAuthStore();
  const logout = useLogout();

  return (
    <AuthSessionTimeoutDialog
      isAuthenticated={isAuthenticated}
      onLogout={() => logout.mutate()}
    />
  );
}
