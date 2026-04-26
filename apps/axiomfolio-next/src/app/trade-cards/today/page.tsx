import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { TradeCardsTodayClient } from "@/components/signals/TradeCardsTodayClient";

export default function TradeCardsTodayPage() {
  return (
    <RequireAuthClient>
      <TradeCardsTodayClient />
    </RequireAuthClient>
  );
}
