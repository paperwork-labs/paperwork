import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { trinketsAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { AuthMarketingNav } from "@/components/clerk/AuthMarketingNav";
import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { TrinketsWordmark } from "@/components/clerk/TrinketsWordmark";

export default function SignUpPage() {
  return (
    <>
      <AuthMarketingNav />
      <ClerkAuthPageShell>
        <SignUpShell
          appName="Trinkets"
          appSlug="trinkets"
          appWordmark={<TrinketsWordmark />}
          appTagline="Tools for FileFree"
          appearance={trinketsAppearance}
        >
          <SignUp />
        </SignUpShell>
      </ClerkAuthPageShell>
    </>
  );
}
