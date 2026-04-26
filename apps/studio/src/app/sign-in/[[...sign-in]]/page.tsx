import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { studioClerkAppearance } from "@/lib/studio-clerk-appearance";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-lg font-medium text-zinc-100">
            Single Sign-On
          </h1>
        </div>
        <SignIn appearance={studioClerkAppearance} />
      </div>
    </ClerkAuthPageShell>
  );
}
