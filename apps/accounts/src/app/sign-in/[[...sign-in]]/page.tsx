import { SignIn } from "@clerk/nextjs";
import { SignInShell } from "@paperwork-labs/auth-clerk/components/sign-in-shell";
import { AccountsAuthPageShell } from "@/components/AccountsAuthPageShell";
import { PaperworkLabsWordmark } from "@/components/PaperworkLabsWordmark";
import { accountsAppearance } from "@paperwork-labs/auth-clerk/appearance";

export default function SignInPage() {
  return (
    <AccountsAuthPageShell>
      <SignInShell
        appName="Paperwork Labs"
        appSlug="accounts"
        appWordmark={<PaperworkLabsWordmark />}
        appTagline="One account, every tool"
        appearance={accountsAppearance}
        isPrimaryHost
      >
        <SignIn />
      </SignInShell>
    </AccountsAuthPageShell>
  );
}
