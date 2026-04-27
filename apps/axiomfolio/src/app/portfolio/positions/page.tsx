import { Suspense } from "react";

import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import PositionsTabShellClient from "@/components/portfolio/PositionsTabShellClient";

export default function PortfolioPositionsPage() {
  return (
    <RequireAuthClient>
      <Suspense fallback={null}>
        <PositionsTabShellClient />
      </Suspense>
    </RequireAuthClient>
  );
}
