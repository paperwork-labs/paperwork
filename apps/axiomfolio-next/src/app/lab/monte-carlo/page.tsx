import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import MonteCarloClient from "@/components/backtest/MonteCarloClient";

export default function MonteCarloPage() {
  return (
    <RequireAuthClient>
      <MonteCarloClient />
    </RequireAuthClient>
  );
}
