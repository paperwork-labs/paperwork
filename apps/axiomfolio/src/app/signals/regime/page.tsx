import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SignalsRegimeClient } from "@/components/signals/SignalsRegimeClient";

export default function SignalsRegimePage() {
  return (
    <RequireAuthClient>
      <SignalsRegimeClient />
    </RequireAuthClient>
  );
}
