import { SignUp } from "@clerk/nextjs";
import { SignUpShell } from "@paperwork-labs/auth-clerk/components/sign-up-shell";
import { AccountsAuthPageShell } from "@/components/AccountsAuthPageShell";
import { PaperworkLabsWordmark } from "@/components/PaperworkLabsWordmark";
import { accountsAppearance } from "@paperwork-labs/auth-clerk/appearance";

export default function SignUpPage() {
  return (
    <AccountsAuthPageShell>
      <SignUpShell
        appName="Paperwork Labs"
        appSlug="accounts"
        appWordmark={<PaperworkLabsWordmark />}
        appTagline="One account, every tool"
        appearance={accountsAppearance}
        isPrimaryHost
      >
        <SignUp />
      </SignUpShell>
    </AccountsAuthPageShell>
  );
}
