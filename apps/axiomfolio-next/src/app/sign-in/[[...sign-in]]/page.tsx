import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { axiomfolioClerkAppearance } from "@/lib/axiomfolio-clerk-appearance";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignIn appearance={axiomfolioClerkAppearance} />
    </ClerkAuthPageShell>
  );
}
