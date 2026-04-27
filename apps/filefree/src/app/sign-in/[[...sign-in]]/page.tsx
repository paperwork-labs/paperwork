import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { fileFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { FileFreeWordmark } from "@/components/clerk/FileFreeWordmark";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <SignInShell
        appName="FileFree"
        appSlug="filefree"
        appWordmark={<FileFreeWordmark />}
        appTagline="Free tax filing"
        appearance={fileFreeAppearance}
      >
        <SignIn />
      </SignInShell>
    </ClerkAuthPageShell>
  );
}
