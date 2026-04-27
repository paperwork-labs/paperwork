import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import ActivityTabShellClient from "@/components/portfolio/ActivityTabShellClient";

export default function PortfolioActivityPage() {
  return (
    <RequireAuthClient>
      <ActivityTabShellClient />
    </RequireAuthClient>
  );
}
