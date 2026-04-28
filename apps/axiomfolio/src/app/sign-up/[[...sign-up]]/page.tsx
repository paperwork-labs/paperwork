import { Suspense } from "react";
import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { axiomfolioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { AxiomFolioWordmark } from "@/components/clerk/AxiomFolioWordmark";
import { SignUpUpgradeCapture } from "@/components/clerk/SignUpUpgradeCapture";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <Suspense fallback={null}>
        <SignUpUpgradeCapture />
      </Suspense>
      <SignUpShell
        appName="AxiomFolio"
        appSlug="axiomfolio"
        appWordmark={<AxiomFolioWordmark />}
        appTagline="Portfolio + signals"
        appearance={axiomfolioAppearance}
      >
        <SignUp />
      </SignUpShell>
    </ClerkAuthPageShell>
  );
}
