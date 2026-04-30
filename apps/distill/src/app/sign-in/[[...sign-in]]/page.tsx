import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { distillAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { AuthMarketingNav } from "@/components/clerk/AuthMarketingNav";
import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { DistillWordmark } from "@/components/clerk/DistillWordmark";

export default function SignInPage() {
  return (
    <>
      <AuthMarketingNav />
      <ClerkAuthPageShell>
        <SignInShell
          appName="Distill"
          appSlug="distill"
          appWordmark={<DistillWordmark />}
          appTagline="Compliance APIs for tax & formation"
          appearance={distillAppearance}
        >
          <SignIn />
        </SignInShell>
      </ClerkAuthPageShell>
    </>
  );
}
