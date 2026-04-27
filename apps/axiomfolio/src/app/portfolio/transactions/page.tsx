import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioTransactionsClient from "@/components/portfolio/PortfolioTransactionsClient";

export default function PortfolioTransactionsPage() {
  return (
    <RequireAuthClient>
      <PortfolioTransactionsClient />
    </RequireAuthClient>
  );
}
