import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { studioAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { StudioSignInBrand } from "@/components/brand/StudioSignInBrand";
import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUpShell
        appName="Studio"
        appSlug="studio"
        appWordmark={<StudioSignInBrand />}
        appTagline="Paperwork Labs admin"
        appearance={studioAppearance}
        variant="admin"
      >
        <SignUp />
      </SignUpShell>
    </ClerkAuthPageShell>
  );
}
