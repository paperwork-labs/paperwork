import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { distillAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { AuthMarketingNav } from "@/components/clerk/AuthMarketingNav";
import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { DistillWordmark } from "@/components/clerk/DistillWordmark";

export default function SignUpPage() {
  return (
    <>
      <AuthMarketingNav />
      <ClerkAuthPageShell>
        <SignUpShell
          appName="Distill"
          appSlug="distill"
          appWordmark={<DistillWordmark />}
          appTagline="Compliance APIs for tax & formation"
          appearance={distillAppearance}
        >
          <SignUp />
        </SignUpShell>
      </ClerkAuthPageShell>
    </>
  );
}
