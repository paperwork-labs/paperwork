import Link from "next/link";

export function AuthMarketingNav() {
  return (
    <nav className="border-b border-stone-800 bg-stone-950/95 px-6 py-4 text-amber-50">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Trinkets
        </Link>
        <div className="flex items-center gap-4 text-sm text-amber-100/80">
          <Link href="/" className="transition hover:text-amber-50">
            Home
          </Link>
          <Link href="/sign-in" className="transition hover:text-amber-50">
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="rounded-full bg-amber-300 px-4 py-2 font-medium text-stone-950 transition hover:bg-amber-200"
          >
            Sign up
          </Link>
        </div>
      </div>
    </nav>
  );
}
