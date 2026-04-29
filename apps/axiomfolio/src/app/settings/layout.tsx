import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SettingsShellClient } from "@/components/settings/SettingsShellClient";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuthClient>
      <SettingsShellClient>{children}</SettingsShellClient>
    </RequireAuthClient>
  );
}
