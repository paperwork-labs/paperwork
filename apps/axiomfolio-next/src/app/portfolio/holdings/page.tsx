import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioHoldingsClient from "@/components/portfolio/PortfolioHoldingsClient";

export default function PortfolioHoldingsPage() {
  return (
    <RequireAuthClient>
      <PortfolioHoldingsClient />
    </RequireAuthClient>
  );
}
