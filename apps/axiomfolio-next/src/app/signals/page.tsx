import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SignalsHubClient } from "@/components/signals/SignalsHubClient";

export default function SignalsPage() {
  return (
    <RequireAuthClient>
      <SignalsHubClient />
    </RequireAuthClient>
  );
}
