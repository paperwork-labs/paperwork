import dynamic from "next/dynamic";
import { RequireAuthClient } from "@/components/auth/RequireAuthClient";

const PortfolioOptionsClient = dynamic(
  () => import("@/components/portfolio/PortfolioOptionsClient"),
  { ssr: false },
);

export default function PortfolioOptionsPage() {
  return (
    <RequireAuthClient>
      <PortfolioOptionsClient />
    </RequireAuthClient>
  );
}
