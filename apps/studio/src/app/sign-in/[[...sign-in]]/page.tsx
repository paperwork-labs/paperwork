import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { studioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { StudioWordmark } from "@/components/clerk/StudioWordmark";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="Studio"
        appSlug="studio"
        appWordmark={<StudioWordmark />}
        appTagline="Paperwork Labs admin tools"
        appearance={studioAppearance}
        variant="admin"
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
