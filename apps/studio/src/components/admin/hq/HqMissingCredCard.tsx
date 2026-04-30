import { AlertTriangle } from "lucide-react";
import Link from "next/link";

export type HqMissingCredCardProps = {
  service: string;
  envVar: string;
  docsLink?: string;
  reconnectAction?: { label: string; href: string };
  description?: string;
};

const DEFAULT_COPY =
  "Set the env var in Vercel / Render then redeploy.";

/** Admin warning when a server env credential is absent — never silent-empty. */
export function HqMissingCredCard({
  service,
  envVar,
  docsLink,
  reconnectAction,
  description,
}: HqMissingCredCardProps) {
  const body =
    description ??
    `We can't load ${service} data because ${envVar} is not set in this environment. ${DEFAULT_COPY}`;

  return (
    <div
      data-testid="hq-missing-cred-card"
      className="rounded-xl border p-4"
      style={{
        borderColor: "rgb(217 119 6 / 0.45)",
        backgroundColor: "rgb(120 53 15 / 0.18)",
      }}
    >
      <div className="flex gap-3">
        <span className="mt-0.5 shrink-0 text-[rgb(253,224,71)]">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium text-[rgb(254,243,199)]">
            {service} · missing <code className="rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">{envVar}</code>
          </p>
          <p className="text-sm leading-relaxed text-[rgb(254,229,199)]">{body}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {reconnectAction ? (
              <Link
                href={reconnectAction.href}
                className="inline-flex rounded-lg bg-[rgb(253,224,71)] px-3 py-1.5 text-sm font-semibold text-zinc-900 transition hover:bg-[rgb(250,204,21)]"
              >
                {reconnectAction.label}
              </Link>
            ) : null}
            {docsLink ? (
              <a
                href={docsLink}
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-lg border border-[rgb(250,204,21)]/50 px-3 py-1.5 text-sm font-medium text-[rgb(254,243,199)] transition hover:bg-black/15"
              >
                Documentation
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
