import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignIn />
    </ClerkAuthPageShell>
  );
}
