import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import SettingsShell from "@/components/settings/SettingsShell";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuthClient>
      <SettingsShell>{children}</SettingsShell>
    </RequireAuthClient>
  );
}
