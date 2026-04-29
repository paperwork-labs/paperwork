"use client";

import { useBackendUser } from "@/hooks/use-backend-user";
import { isPlatformAdminRole } from "@/utils/userRole";

import { SettingsShell } from "./SettingsShellNext";
import { AXIOMFOLIO_SETTINGS_CLUSTERS } from "./SettingsShell.config";

export function SettingsShellClient({ children }: { children: React.ReactNode }) {
  const { user } = useBackendUser();
  return (
    <SettingsShell
      clusters={AXIOMFOLIO_SETTINGS_CLUSTERS}
      useAdminGate={() => isPlatformAdminRole(user?.role)}
    >
      {children}
    </SettingsShell>
  );
}
