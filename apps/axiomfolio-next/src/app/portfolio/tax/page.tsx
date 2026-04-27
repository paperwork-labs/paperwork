import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioTaxCenterClient from "@/components/portfolio/PortfolioTaxCenterClient";

export default function PortfolioTaxPage() {
  return (
    <RequireAuthClient>
      <PortfolioTaxCenterClient />
    </RequireAuthClient>
  );
}
