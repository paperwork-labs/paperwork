"use client";

import Link from "next/link";

import { SettingsShell } from "@paperwork-labs/ui";

import { useBackendUser } from "@/hooks/use-backend-user";
import { isPlatformAdminRole } from "@/utils/userRole";

import { AXIOMFOLIO_SETTINGS_CLUSTERS } from "./SettingsShell.config";

export function SettingsShellClient({ children }: { children: React.ReactNode }) {
  const { user } = useBackendUser();
  return (
    <SettingsShell
      clusters={AXIOMFOLIO_SETTINGS_CLUSTERS}
      LinkComponent={Link}
      useAdminGate={() => isPlatformAdminRole(user?.role)}
    >
      {children}
    </SettingsShell>
  );
}
