export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background text-foreground">
      <div className="flex flex-col items-center gap-4 text-center">
        <h1 className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-5xl font-bold tracking-tight text-transparent md:text-6xl">
          FileFree
        </h1>
        <p className="text-lg text-muted-foreground md:text-xl">
          Free AI-powered tax filing. Seriously.
        </p>
        <p className="mt-8 text-sm text-muted-foreground/60">
          Landing page coming soon &mdash; filefree.tax
        </p>
      </div>
    </main>
  );
}
