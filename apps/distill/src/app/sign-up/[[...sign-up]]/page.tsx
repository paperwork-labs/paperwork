import { SignUp } from "@clerk/nextjs";

import { ClerkAuthPageShell } from "@/components/clerk/ClerkAuthPageShell";
import { distillClerkAppearance } from "@/lib/clerk-appearance";

export default function SignUpPage() {
  return (
    <ClerkAuthPageShell>
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-400/90">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-lg font-medium text-slate-100">
            Single Sign-On
          </h1>
        </div>
        <SignUp appearance={distillClerkAppearance} />
      </div>
    </ClerkAuthPageShell>
  );
}
