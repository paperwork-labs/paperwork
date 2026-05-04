import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";
import type { BrainTranscriptDetail } from "@/types/brain-transcripts";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

async function fetchDetail(
  auth: { root: string; secret: string },
  id: string,
): Promise<BrainTranscriptDetail | null> {
  try {
    const res = await fetch(`${auth.root}/admin/transcripts/${encodeURIComponent(id)}`, {
      headers: { "X-Brain-Secret": auth.secret },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = (await res.json()) as { success?: boolean; data?: unknown };
    if (!json.success || typeof json.data !== "object" || json.data === null) return null;
    return json.data as BrainTranscriptDetail;
  } catch {
    return null;
  }
}

export default async function TranscriptDetailPage({ params }: Props) {
  const { id } = await params;
  const auth = getBrainAdminFetchOptions();

  if (!auth.ok) {
    return (
      <div className="rounded-xl border border-red-900/40 bg-red-500/5 p-8 text-center">
        <p className="text-sm text-red-400">Brain API not configured.</p>
      </div>
    );
  }

  const detail = await fetchDetail(auth, id);

  if (!detail) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8 md:px-6">
        <BackLink />
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-10 text-center">
          <p className="text-sm font-medium text-zinc-400">Transcript not found</p>
          <p className="mt-1 text-xs text-zinc-600">
            ID <code className="text-zinc-500">{id}</code> is missing or not yet ingested.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 md:px-6">
      <BackLink />

      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50 md:text-3xl">
          Transcript
        </h1>
        <p className="text-base text-zinc-300">{detail.title}</p>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-zinc-500">
          <div>
            <dt className="inline font-medium text-zinc-600">Session</dt>{" "}
            <dd className="inline font-mono text-zinc-400">{detail.session_id}</dd>
          </div>
          <div>
            <dt className="inline font-medium text-zinc-600">Messages</dt>{" "}
            <dd className="inline tabular-nums text-zinc-400">{detail.message_count}</dd>
          </div>
        </dl>
        {detail.tags.length > 0 ? (
          <p className="text-xs text-zinc-500">{detail.tags.join(" · ")}</p>
        ) : null}
      </header>

      <div className="space-y-6">
        {detail.messages.map((m) => (
          <article
            key={m.turn_index}
            className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 md:p-5"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Turn {m.turn_index}{" "}
              <span className="font-normal text-zinc-600">· {m.ingested_at}</span>
            </p>
            {m.summary ? (
              <p className="mt-2 text-xs italic text-zinc-400">{m.summary}</p>
            ) : null}
            <div className="mt-4 space-y-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400/90">
                  User
                </p>
                <pre className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-950/80 p-3 font-mono text-xs leading-relaxed text-zinc-200">
                  {m.user_message}
                </pre>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-400/90">
                  Assistant
                </p>
                <pre className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-950/80 p-3 font-mono text-xs leading-relaxed text-zinc-200">
                  {m.assistant_message}
                </pre>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/admin/transcripts"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-1 text-sm text-zinc-500 transition hover:text-zinc-300"
    >
      <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
      Back to transcripts
    </Link>
  );
}
