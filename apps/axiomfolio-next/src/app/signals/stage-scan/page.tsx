import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SignalsStageScanClient } from "@/components/signals/SignalsStageScanClient";

export default function SignalsStageScanPage() {
  return (
    <RequireAuthClient>
      <SignalsStageScanClient />
    </RequireAuthClient>
  );
}
