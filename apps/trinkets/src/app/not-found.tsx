import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <div className="mx-auto max-w-md text-center">
        <p className="text-6xl font-bold tracking-tight text-amber-500">404</p>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">
          Page not found
        </h1>
        <p className="mt-2 text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded-lg bg-amber-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-amber-500"
        >
          Back to Trinkets
        </Link>
      </div>
    </main>
  );
}
