import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { launchFreeAppearance } from "@paperwork-labs/auth-clerk/appearance";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { LaunchFreeWordmark } from "@/components/clerk/LaunchFreeWordmark";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <SignUpShell
        appName="LaunchFree"
        appSlug="launchfree"
        appWordmark={<LaunchFreeWordmark />}
        appTagline="Free LLC formation"
        appearance={launchFreeAppearance}
      >
        <SignUp />
      </SignUpShell>
    </ClerkAuthPageShell>
  );
}
