import { SignUp } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { axiomfolioClerkAppearance } from "@/lib/axiomfolio-clerk-appearance";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-lg font-medium text-foreground">
            Single Sign-On
          </h1>
        </div>
        <SignUp appearance={axiomfolioClerkAppearance} />
      </div>
    </ClerkAuthPageShell>
  );
}
