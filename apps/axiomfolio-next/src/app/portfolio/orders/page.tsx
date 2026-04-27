import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioOrdersClient from "@/components/portfolio/PortfolioOrdersClient";

export default function PortfolioOrdersPage() {
  return (
    <RequireAuthClient>
      <PortfolioOrdersClient />
    </RequireAuthClient>
  );
}
