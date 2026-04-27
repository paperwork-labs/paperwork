import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioWorkspaceClient from "@/components/market/PortfolioWorkspaceClient";

export default function MarketWorkspacePage() {
  return (
    <RequireAuthClient>
      <PortfolioWorkspaceClient />
    </RequireAuthClient>
  );
}
