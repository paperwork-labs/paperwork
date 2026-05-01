"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MessageSquare, Plus } from "lucide-react";

import { ComposeModal, type ComposeModalPrefill } from "@/app/admin/brain/conversations/compose-modal";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import {
  type ComposePersonaOption,
  resolveComposePersonaOptions,
} from "@/lib/compose-persona-options";
import type {
  BrainConversationsResponse,
  Conversation,
  ConversationSentiment,
  ConversationSpace,
  StatusLevel,
} from "@/types/conversations";

const VALID_SPACE: readonly ConversationSpace[] = [
  "personal",
  "paperwork-labs",
  "axiomfolio",
  "filefree",
  "runbook-asks",
  "incidents",
] as const;

function spaceForProductSlug(slug: string): ConversationSpace {
  return (VALID_SPACE as readonly string[]).includes(slug) ? (slug as ConversationSpace) : "paperwork-labs";
}

function statusLabel(s: StatusLevel): string {
  switch (s) {
    case "needs-action":
      return "Needs action";
    case "open":
      return "Open";
    case "snoozed":
      return "Snoozed";
    case "resolved":
      return "Resolved";
    case "archived":
      return "Archived";
    default: {
      const _x: never = s;
      return _x;
    }
  }
}

function SentimentBadge({ sentiment }: { sentiment: ConversationSentiment | null | undefined }) {
  const tone = sentiment ?? "neutral";
  const cls =
    tone === "positive"
      ? "border-emerald-500/45 bg-emerald-950/35 text-emerald-200"
      : tone === "negative"
        ? "border-red-500/45 bg-red-950/35 text-red-200"
        : "border-zinc-600 bg-zinc-900/60 text-zinc-400";
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}
      data-testid="support-sentiment-badge"
      data-sentiment={tone}
    >
      {tone}
    </span>
  );
}

type Props = {
  productSlug: string;
  productName: string;
};

export function ProductSupportPanel({ productSlug, productName }: Props) {
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [personaOptions, setPersonaOptions] = useState<ComposePersonaOption[]>([]);
  const [composeOpen, setComposeOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        filter: "all",
        limit: "200",
        product_slug: productSlug,
      });
      const res = await fetch(`/api/admin/conversations?${params}`);
      const json = (await res.json()) as BrainConversationsResponse;
      if (!json.success || !json.data) {
        setError(json.error ?? "Could not load conversations.");
        setItems([]);
        return;
      }
      const filtered = json.data.items.filter((c) => (c.product_slug ?? "") === productSlug);
      setItems(filtered);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [productSlug]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    void resolveComposePersonaOptions().then((opts) => {
      if (!cancelled) setPersonaOptions(opts);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const prefill = useMemo<ComposeModalPrefill>(() => {
    const space = spaceForProductSlug(productSlug);
    return {
      title: "",
      bodyMd: `**Product:** ${productName} (\`${productSlug}\`)\n\n`,
      space,
      productSlug,
      tags: `support, ${productSlug}`,
    };
  }, [productName, productSlug]);

  const sorted = useMemo(
    () => [...items].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1)),
    [items],
  );

  return (
    <div className="space-y-4" data-testid="product-support-inbox">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--status-muted)]">
          Support tickets routed to <code className="text-zinc-300">{productSlug}</code>
        </p>
        <button
          type="button"
          data-testid="product-support-new-ticket"
          onClick={() => setComposeOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/35 bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-200 ring-1 ring-sky-500/25 transition hover:bg-sky-500/25"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          New ticket
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--status-muted)]" aria-busy="true">
          Loading inbox…
        </p>
      ) : error ? (
        <HqEmptyState title="Could not load inbox" description={error} />
      ) : sorted.length === 0 ? (
        <HqEmptyState
          icon={<MessageSquare className="h-10 w-10" aria-hidden />}
          title="No support tickets yet"
          description={`Nothing shows for ${productName} yet (check product_slug routing). Create a ticket to capture customer context.`}
          action={{ label: "New ticket", onClick: () => setComposeOpen(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {sorted.map((c) => (
            <li key={c.id}>
              <Link
                href={`/admin/conversations/${c.id}`}
                data-testid="support-ticket-row"
                className="flex flex-col gap-2 rounded-xl border border-zinc-800/90 bg-zinc-950/45 px-4 py-3 transition hover:border-zinc-700/90 hover:bg-zinc-950/70"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="text-sm font-medium text-zinc-100">{c.title}</span>
                  <span className="rounded-full border border-zinc-700 bg-zinc-900/70 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-400">
                    {statusLabel(c.status)}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <SentimentBadge sentiment={c.sentiment ?? null} />
                  {c.persona ? (
                    <span className="rounded-full border border-zinc-700/80 bg-zinc-900/50 px-2 py-0.5 text-[10px] font-medium text-zinc-400">
                      Persona: <span className="text-zinc-200">{c.persona}</span>
                    </span>
                  ) : (
                    <span className="text-[10px] text-zinc-600">No persona tag</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {composeOpen ? (
        <ComposeModal
          prefill={prefill}
          personaOptions={personaOptions}
          onClose={() => setComposeOpen(false)}
          onSuccess={() => {
            setComposeOpen(false);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
