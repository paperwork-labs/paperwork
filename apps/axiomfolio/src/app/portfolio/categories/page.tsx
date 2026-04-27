import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioCategoriesClient from "@/components/portfolio/PortfolioCategoriesClient";

export default function PortfolioCategoriesPage() {
  return (
    <RequireAuthClient>
      <PortfolioCategoriesClient />
    </RequireAuthClient>
  );
}
