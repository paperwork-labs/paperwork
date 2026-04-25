import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SignalsPicksClient } from "@/components/signals/SignalsPicksClient";

export default function SignalsPicksPage() {
  return (
    <RequireAuthClient>
      <SignalsPicksClient />
    </RequireAuthClient>
  );
}
