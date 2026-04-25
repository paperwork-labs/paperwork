import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MarketDashboardClient from "@/components/market/MarketDashboardClient";

export default function MarketDashboardPage() {
  return (
    <RequireAuthClient>
      <MarketDashboardClient />
    </RequireAuthClient>
  );
}
