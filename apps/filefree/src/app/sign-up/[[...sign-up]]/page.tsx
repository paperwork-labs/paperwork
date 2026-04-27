import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { fileFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { FileFreeWordmark } from "@/components/clerk/FileFreeWordmark";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUpShell
        appName="FileFree"
        appSlug="filefree"
        appWordmark={<FileFreeWordmark />}
        appTagline="Free tax filing"
        appearance={fileFreeAppearance}
      >
        <SignUp />
      </SignUpShell>
    </ClerkAuthPageShell>
  );
}
