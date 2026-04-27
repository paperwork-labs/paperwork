import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { studioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { StudioWordmark } from "@/components/clerk/StudioWordmark";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUpShell
        appName="Studio"
        appSlug="studio"
        appWordmark={<StudioWordmark />}
        appTagline="Paperwork Labs admin"
        appearance={studioAppearance}
        variant="admin"
      >
        <SignUp />
      </SignUpShell>
    </ClerkAuthPageShell>
  );
}
