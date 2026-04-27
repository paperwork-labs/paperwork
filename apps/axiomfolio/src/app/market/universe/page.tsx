import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MarketTrackedClient from "@/components/market/MarketTrackedClient";

export default function MarketUniversePage() {
  return (
    <RequireAuthClient>
      <MarketTrackedClient />
    </RequireAuthClient>
  );
}
