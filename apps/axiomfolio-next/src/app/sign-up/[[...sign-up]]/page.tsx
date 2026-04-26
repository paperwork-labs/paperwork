import { SignUp } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { axiomfolioClerkAppearance } from "@/lib/axiomfolio-clerk-appearance";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUp appearance={axiomfolioClerkAppearance} />
    </ClerkAuthPageShell>
  );
}
