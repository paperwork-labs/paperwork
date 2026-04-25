import { SignUp } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <SignUp />
      </div>
    </ClerkAuthPageShell>
  );
}
