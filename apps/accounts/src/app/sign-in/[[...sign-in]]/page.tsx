import { SignIn } from "@clerk/nextjs";
import { accountsClerkAppearance } from "@/lib/accounts-clerk-appearance";

export default function SignInPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-[#0F172A] px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Paperwork Labs
          </p>
          <h1 className="mt-1 text-xl font-semibold text-[#F8FAFC]">
            Sign in to Paperwork ID
          </h1>
        </div>
        <SignIn appearance={accountsClerkAppearance} />
      </div>
    </main>
  );
}
