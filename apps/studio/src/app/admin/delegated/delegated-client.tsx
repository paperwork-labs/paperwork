"use client";

import { useMemo, useState } from "react";
import { Ban, Droplets } from "lucide-react";

import type { DelegatedShare } from "@/types/circles";

function formatExpiry(iso: string | null): string {
  if (iso == null) return "No expiry";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function DelegatedAccessClient({ shares }: { shares: DelegatedShare[] }) {
  const activeInitial = useMemo(
    () => shares.filter((s) => s.expires_at == null || Date.parse(s.expires_at) > Date.now()),
    [shares],
  );
  const [revokedIds, setRevokedIds] = useState<Set<string>>(() => new Set());

  const visible = activeInitial.filter((s) => !revokedIds.has(s.id));

  return (
    <ul className="space-y-3" data-testid="delegated-shares-list">
      {visible.length === 0 ? (
        <li className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 px-5 py-8 text-center text-sm text-zinc-500">
          No active delegated shares.
        </li>
      ) : (
        visible.map((share) => (
          <li key={share.id}>
            <article
              data-testid={`delegated-share-${share.id}`}
              className="flex flex-col gap-4 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-zinc-100">{share.delegate_name}</h2>
                  <span className="rounded-md border border-zinc-700/80 bg-zinc-950/60 px-2 py-0.5 font-mono text-[10px] text-zinc-500">
                    {share.delegate_id}
                  </span>
                  {share.watermark ? (
                    <span className="inline-flex items-center gap-1 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-200">
                      <Droplets className="h-3 w-3" aria-hidden />
                      Watermark
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-zinc-500">
                  Owner <span className="text-zinc-400">{share.owner_id}</span>
                  {" · "}
                  Expires {formatExpiry(share.expires_at)}
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {share.scope.map((perm) => (
                    <li key={perm}>
                      <span className="inline-block rounded-md border border-zinc-700/60 bg-zinc-950/50 px-2 py-0.5 font-mono text-[11px] text-zinc-400">
                        {perm}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
                <button
                  type="button"
                  data-testid={`revoke-share-${share.id}`}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-200 transition hover:border-red-400/60 hover:bg-red-500/15"
                  onClick={() =>
                    setRevokedIds((prev) => new Set(prev).add(share.id))
                  }
                >
                  <Ban className="h-4 w-4 shrink-0" aria-hidden />
                  Revoke
                </button>
                <p className="text-center text-[10px] text-zinc-600 sm:text-right">
                  UI only — not persisted
                </p>
              </div>
            </article>
          </li>
        ))
      )}
    </ul>
  );
}
