import { SignIn } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { trinketsClerkAppearance } from "@/lib/trinkets-clerk-appearance";

export default function SignInPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-300/90">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-lg font-medium text-stone-100">
            Single Sign-On
          </h1>
        </div>
        <SignIn appearance={trinketsClerkAppearance} />
      </div>
    </ClerkAuthPageShell>
  );
}
