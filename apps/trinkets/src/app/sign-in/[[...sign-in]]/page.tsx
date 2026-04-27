import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { trinketsAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { TrinketsWordmark } from "@/components/clerk/TrinketsWordmark";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="Trinkets"
        appSlug="trinkets"
        appWordmark={<TrinketsWordmark />}
        appTagline="Personalized gift discovery"
        appearance={trinketsAppearance}
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
