import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { ShadowTradesClient } from "@/components/signals/ShadowTradesClient";

export default function ShadowTradesPage() {
  return (
    <RequireAuthClient>
      <ShadowTradesClient />
    </RequireAuthClient>
  );
}
