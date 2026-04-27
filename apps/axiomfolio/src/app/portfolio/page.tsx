import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioTabShellClient from "@/components/portfolio/PortfolioTabShellClient";

export default function PortfolioPage() {
  return (
    <RequireAuthClient>
      <PortfolioTabShellClient />
    </RequireAuthClient>
  );
}
