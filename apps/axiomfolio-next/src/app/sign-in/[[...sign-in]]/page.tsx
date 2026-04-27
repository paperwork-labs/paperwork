import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { axiomfolioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { AxiomFolioWordmark } from "@/components/clerk/AxiomFolioWordmark";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="AxiomFolio"
        appSlug="axiomfolio"
        appWordmark={<AxiomFolioWordmark />}
        appTagline="Portfolio + signals"
        appearance={axiomfolioAppearance}
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
