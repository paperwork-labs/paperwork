import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioIncomeClient from "@/components/portfolio/PortfolioIncomeClient";

export default function PortfolioIncomePage() {
  return (
    <RequireAuthClient>
      <PortfolioIncomeClient />
    </RequireAuthClient>
  );
}
