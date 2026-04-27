import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { studioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { StudioSignInBrand } from "@/components/brand/StudioSignInBrand";
import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="Studio"
        appSlug="studio"
        appWordmark={<StudioSignInBrand />}
        appTagline="Paperwork Labs admin"
        appearance={studioAppearance}
        variant="admin"
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
