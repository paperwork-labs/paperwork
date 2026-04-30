import Link from "next/link";

export function AuthMarketingNav() {
  return (
    <nav className="border-b border-slate-800 bg-slate-950/95 px-6 py-4 text-slate-100">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          LaunchFree
        </Link>
        <div className="flex items-center gap-4 text-sm text-slate-300">
          <Link href="/" className="transition hover:text-white">
            Home
          </Link>
          <Link href="/sign-in" className="transition hover:text-white">
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="rounded-full bg-cyan-400 px-4 py-2 font-medium text-slate-950 transition hover:bg-cyan-300"
          >
            Sign up
          </Link>
        </div>
      </div>
    </nav>
  );
}
