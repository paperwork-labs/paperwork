"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { isPlatformAdminRole } from "@/utils/userRole";

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!ready) return;
    if (!isPlatformAdminRole(user?.role)) {
      router.replace("/");
    }
  }, [ready, user?.role, router]);

  if (!ready) {
    return null;
  }
  if (!isPlatformAdminRole(user?.role)) {
    return null;
  }
  return <>{children}</>;
}

export default RequireAdmin;
