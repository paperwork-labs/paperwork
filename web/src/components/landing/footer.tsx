import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border/50 px-4 py-12">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-6">
        <div className="flex items-center gap-6 text-sm text-muted-foreground">
          <a
            href="https://tiktok.com/@filefree"
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-foreground"
          >
            TikTok
          </a>
          <a
            href="https://instagram.com/filefree.tax"
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-foreground"
          >
            Instagram
          </a>
          <a
            href="https://x.com/filefreetax"
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-foreground"
          >
            X
          </a>
        </div>

        <div className="flex items-center gap-6 text-xs text-muted-foreground/60">
          <Link href="/privacy" className="transition hover:text-foreground">
            Privacy
          </Link>
          <Link href="/terms" className="transition hover:text-foreground">
            Terms
          </Link>
        </div>

        <p className="text-xs text-muted-foreground/40">
          &copy; {new Date().getFullYear()} FileFree. Free tax filing, forever.
        </p>
      </div>
    </footer>
  );
}
