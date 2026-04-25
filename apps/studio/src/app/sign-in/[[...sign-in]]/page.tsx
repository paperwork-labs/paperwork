import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <SignIn />
      </div>
    </ClerkAuthPageShell>
  );
}
