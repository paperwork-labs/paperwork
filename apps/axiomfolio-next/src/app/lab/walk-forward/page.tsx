import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import WalkForwardClient from "@/components/backtest/WalkForwardClient";

export default function WalkForwardPage() {
  return (
    <RequireAuthClient>
      <WalkForwardClient />
    </RequireAuthClient>
  );
}
