import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { PortfolioOptionsLazy } from "@/components/portfolio/PortfolioOptionsLazy";

export default function PortfolioOptionsPage() {
  return (
    <RequireAuthClient>
      <PortfolioOptionsLazy />
    </RequireAuthClient>
  );
}
