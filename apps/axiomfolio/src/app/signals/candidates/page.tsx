import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import { SignalsCandidatesClient } from "@/components/signals/SignalsCandidatesClient";

export default function SignalsCandidatesPage() {
  return (
    <RequireAuthClient>
      <SignalsCandidatesClient />
    </RequireAuthClient>
  );
}
