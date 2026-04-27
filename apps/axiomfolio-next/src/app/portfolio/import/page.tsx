import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PortfolioImportClient from "@/components/portfolio/PortfolioImportClient";

export default function PortfolioImportPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={null}>
        <PortfolioImportClient />
      </Suspense>
    </RequireAuthClient>
  );
}
