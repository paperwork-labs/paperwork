import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { launchFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { LaunchFreeWordmark } from "@/components/clerk/LaunchFreeWordmark";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="LaunchFree"
        appSlug="launchfree"
        appWordmark={<LaunchFreeWordmark />}
        appTagline="Free LLC formation"
        appearance={launchFreeAppearance}
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
