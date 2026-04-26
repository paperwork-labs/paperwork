import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { launchFreeClerkAppearance } from "@/lib/launchfree-clerk-appearance";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-400/85">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-lg font-medium text-slate-100">
            Single Sign-On
          </h1>
        </div>
        <SignIn appearance={launchFreeClerkAppearance} />
      </div>
    </ClerkAuthPageShell>
  );
}
