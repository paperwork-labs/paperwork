import { SignUp } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUp />
    </ClerkAuthPageShell>
  );
}
