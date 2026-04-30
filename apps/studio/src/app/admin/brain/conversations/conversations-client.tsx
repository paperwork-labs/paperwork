"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Archive,
  Bell,
  BellOff,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  MessageSquare,
  Paperclip,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
} from "lucide-react";
import type {
  Conversation,
  ConversationsListPage,
  FilterChip,
  StatusLevel,
  ThreadMessage,
  UrgencyLevel,
} from "@/types/conversations";
import { AppBadgeManager, useUnreadCount } from "@/components/pwa/AppBadgeManager";
import { isPushSupported } from "@/lib/web-push";
import { ExpenseConversationCard } from "@/components/admin/ExpenseConversationCard";
import { HqErrorState } from "@/components/admin/hq/HqErrorState";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { ComposeModal } from "./compose-modal";
import { SnoozePicker } from "./snooze-picker";

const FILTER_LABELS: Record<FilterChip, string> = {
  "needs-action": "Needs action",
  open: "Open",
  snoozed: "Snoozed",
  resolved: "Resolved",
  all: "All",
};

const URGENCY_DOT: Record<UrgencyLevel, string> = {
  info: "bg-zinc-500",
  normal: "bg-sky-400",
  high: "bg-amber-400",
  critical: "bg-red-500",
};

const URGENCY_LABEL: Record<UrgencyLevel, string> = {
  info: "info",
  normal: "normal",
  high: "high",
  critical: "critical",
};

function attachmentDescription(
  att: Conversation["messages"][0]["attachments"][0],
): string {
  try {
    const u = new URL(att.url);
    const seg = u.pathname.split("/").filter(Boolean).pop();
    if (seg) return decodeURIComponent(seg);
  } catch {
    /* ignore */
  }
  if (att.mime) return att.mime;
  return "attachment";
}

function UrgencyDot({ urgency }: { urgency: UrgencyLevel }) {
  return (
    <span
      className={`mt-1 h-2 w-2 shrink-0 rounded-full ${URGENCY_DOT[urgency]}`}
      title={URGENCY_LABEL[urgency]}
    />
  );
}

function AttachmentThumb({ att }: { att: Conversation["messages"][0]["attachments"][0] }) {
  if (att.kind === "image" && (att.thumbnail_url ?? att.url)) {
    return (
      <a href={att.url} target="_blank" rel="noreferrer">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={att.thumbnail_url ?? att.url}
          alt={attachmentDescription(att)}
          className="h-16 w-16 rounded object-cover"
        />
      </a>
    );
  }
  return (
    <a
      href={att.url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center gap-1 rounded bg-zinc-800 px-2 py-1 text-xs text-zinc-300 hover:text-zinc-100"
    >
      <Paperclip className="h-3 w-3" />
      {att.mime ?? "file"}
    </a>
  );
}

function MessageBubble({ msg }: { msg: ThreadMessage }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-zinc-300">
          {msg.author.display_name ?? msg.author.id}
        </span>
        <span className="text-[10px] text-zinc-600">
          {new Date(msg.created_at).toLocaleString()}
        </span>
      </div>
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 px-4 py-3">
        <div className="prose prose-invert prose-sm max-w-none text-zinc-300 prose-p:my-1 prose-a:text-sky-400 prose-code:rounded prose-code:bg-zinc-800 prose-code:px-1">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.body_md}</ReactMarkdown>
        </div>
        {msg.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {msg.attachments.map((att) => (
              <AttachmentThumb key={att.id} att={att} />
            ))}
          </div>
        )}
        {Object.keys(msg.reactions).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(msg.reactions).map(([emoji, reactors]) => (
              <span
                key={emoji}
                className="rounded-full bg-zinc-800 px-2 py-0.5 text-sm"
                title={reactors.join(", ")}
              >
                {emoji} {reactors.length}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(path, opts);
  return res.json();
}

interface Props {
  brainConfigured: boolean;
  initialPage: ConversationsListPage | null;
  /** Founder-actions source or Brain backfill/list failure — no silent empty inbox. */
  setupError?: string | null;
}

export function ConversationsClient({
  brainConfigured,
  initialPage,
  setupError = null,
}: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [activeFilter, setActiveFilter] = useState<FilterChip>("needs-action");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>(
    initialPage?.items ?? [],
  );
  const [filterCounts, setFilterCounts] = useState<Partial<Record<FilterChip, number>>>({
    "needs-action": initialPage?.total ?? 0,
  });
  const [nextCursor, setNextCursor] = useState<string | null>(initialPage?.next_cursor ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replyLoading, setReplyLoading] = useState(false);
  const [showCompose, setShowCompose] = useState(false);
  const [snoozingId, setSnoozingId] = useState<string | null>(null);
  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (searchParams.get("compose") !== "1") return;
    setShowCompose(true);
    router.replace(pathname, { scroll: false });
  }, [searchParams, router, pathname]);

  // Debounce search input
  useEffect(() => {
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => {
      if (searchRef.current) clearTimeout(searchRef.current);
    };
  }, [search]);

  const fetchPage = useCallback(
    async (filter: FilterChip, q: string, cursor?: string) => {
      if (!brainConfigured) return;
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ filter, limit: "50" });
        if (q) params.set("search", q);
        if (cursor) params.set("cursor", cursor);
        const json = await apiFetch(`/api/admin/conversations?${params}`);
        if (!json.success) {
          setError(json.error ?? "Unknown error from Brain");
          return;
        }
        const page: ConversationsListPage = json.data;
        setConversations((prev) =>
          cursor ? [...prev, ...page.items] : page.items,
        );
        setNextCursor(page.next_cursor);
        setFilterCounts((prev) => ({ ...prev, [filter]: page.total }));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Network error");
      } finally {
        setLoading(false);
      }
    },
    [brainConfigured],
  );

  // Refetch when filter or search changes
  useEffect(() => {
    if (setupError) return;
    setConversations([]);
    setNextCursor(null);
    void fetchPage(activeFilter, debouncedSearch);
  }, [activeFilter, debouncedSearch, fetchPage, setupError]);

  // 60s cadence: backfill (idempotent) then refresh; pause interval while tab hidden (Page Visibility).
  useEffect(() => {
    if (!brainConfigured || setupError) return;

    const POLL_MS = 60_000;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const run = () => {
      if (document.visibilityState === "hidden") return;
      void (async () => {
        try {
          await fetch("/api/admin/conversations/backfill", { method: "POST" });
        } catch {
          /* surfaced on fetchPage */
        }
        await fetchPage(activeFilter, debouncedSearch);
      })();
    };

    const armInterval = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
      if (document.visibilityState !== "visible") return;
      intervalId = setInterval(run, POLL_MS);
    };

    armInterval();
    document.addEventListener("visibilitychange", armInterval);
    return () => {
      document.removeEventListener("visibilitychange", armInterval);
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeFilter, debouncedSearch, brainConfigured, fetchPage, setupError]);

  const loadMore = () => {
    if (nextCursor && !loading) {
      void fetchPage(activeFilter, debouncedSearch, nextCursor);
    }
  };

  const updateSelectedFromList = (updated: Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    if (selected?.id === updated.id) setSelected(updated);
  };

  const handleStatusAction = async (
    conversationId: string,
    status: StatusLevel,
  ) => {
    const json = await apiFetch(`/api/admin/conversations/${conversationId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (json.success && json.data) updateSelectedFromList(json.data);
  };

  const handleReply = async () => {
    if (!selected || !replyText.trim()) return;
    setReplyLoading(true);
    try {
      const json = await apiFetch(`/api/admin/conversations/${selected.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: { id: "founder", kind: "founder", display_name: "Founder" },
          body_md: replyText.trim(),
          attachments: [],
        }),
      });
      if (json.success) {
        setReplyText("");
        // Refresh the selected conversation
        const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
        if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
      }
    } finally {
      setReplyLoading(false);
    }
  };

  const handleSnooze = async (conversationId: string, until: Date) => {
    const json = await apiFetch(`/api/admin/conversations/${conversationId}/snooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ until: until.toISOString() }),
    });
    if (json.success && json.data) updateSelectedFromList(json.data);
    setSnoozingId(null);
  };

  const handleComposeSuccess = (conv: Conversation) => {
    setConversations((prev) => [conv, ...prev]);
    setSelected(conv);
    setShowCompose(false);
  };

  if (setupError) {
    const looksLikeBrainAuth =
      /secret|401|403|unauthorized|forbidden|x-brain-secret/i.test(setupError);
    return (
      <div data-testid="conversations-setup-error" className="space-y-4">
        {looksLikeBrainAuth ? (
          <HqMissingCredCard
            service="Brain Conversations"
            envVar="BRAIN_API_SECRET"
            description="Studio could not authorize to Brain for this page. Check Brain admin secret matches deployment."
          />
        ) : null}
        <HqErrorState
          title="Conversations could not finish setup"
          description="Retry reloads the page and re-runs founder-actions validation plus Brain backfill."
          error={setupError}
          onRetry={() => window.location.reload()}
          icon={<AlertTriangle className="h-6 w-6" aria-hidden />}
        />
      </div>
    );
  }

  if (!brainConfigured) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-8 text-center">
        <p className="text-sm text-zinc-400">
          Brain is not configured. Set{" "}
          <code className="text-zinc-300">BRAIN_API_URL</code> and{" "}
          <code className="text-zinc-300">BRAIN_API_SECRET</code> to enable Conversations.
        </p>
      </div>
    );
  }

  const filters: FilterChip[] = ["needs-action", "open", "snoozed", "resolved", "all"];

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col gap-4 overflow-hidden">
      {/* Badge manager — mounts silently, clears badge since inbox is open */}
      <AppBadgeManager clearOnMount />
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <MessageSquare className="h-5 w-5 text-sky-400" />
          <h1 className="text-xl font-semibold text-zinc-100">Conversations</h1>
          <PushBadgePill />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void fetchPage(activeFilter, debouncedSearch)}
            disabled={loading}
            className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-40"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowCompose(true)}
            className="flex items-center gap-1.5 rounded-lg bg-sky-500/15 px-3 py-1.5 text-sm font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/25"
          >
            <Plus className="h-4 w-4" />
            Compose
          </button>
        </div>
      </div>

      {/* Filter chips + search */}
      <div className="flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center">
        <div className="flex flex-wrap items-center gap-2">
        {filters.map((f) => {
          const count = filterCounts[f];
          return (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition ${
                activeFilter === f
                  ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              }`}
            >
              {FILTER_LABELS[f]}
              {count !== undefined && count > 0 && (
                <span className="rounded-full bg-zinc-700 px-1.5 py-0.5 text-[10px] tabular-nums text-zinc-200">
                  {count}
                </span>
              )}
            </button>
          );
        })}
        </div>
        <div className="relative w-full md:ml-auto md:w-60">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="h-8 w-full rounded-lg border border-zinc-800 bg-zinc-900 pl-8 pr-3 text-sm text-zinc-300 placeholder-zinc-600 outline-none focus:border-sky-500/50"
          />
        </div>
      </div>

      {error && (
        <div
          data-testid="conversations-error"
          className="rounded-lg border border-red-800/60 bg-red-900/20 p-3 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      {/* 2-pane layout — single pane on small screens */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row">
        {/* Left inbox */}
        <div
          className={`flex min-h-0 flex-col overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/40 md:w-80 md:shrink-0 ${
            selected ? "hidden min-h-0 md:flex" : "flex w-full min-h-0 flex-1"
          }`}
        >
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading && conversations.length === 0 ? (
              <div data-testid="conversations-loading" className="p-6 text-center text-sm text-zinc-500">
                Loading…
              </div>
            ) : conversations.length === 0 ? (
              <EmptyState filter={activeFilter} search={debouncedSearch} />
            ) : (
              <ul role="list" data-testid="conversations-inbox-list" className="divide-y divide-zinc-800/60">
                {conversations.map((conv) => (
                  <li key={conv.id}>
                    <button
                      onClick={() => setSelected(conv)}
                      className={`flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-zinc-800/50 ${
                        selected?.id === conv.id ? "bg-zinc-800/70" : ""
                      }`}
                    >
                      <UrgencyDot urgency={conv.urgency} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-zinc-100">
                          {conv.title}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-zinc-500">
                          {new Date(conv.updated_at).toLocaleDateString()}
                          {conv.persona ? ` · ${conv.persona}` : ""}
                        </p>
                        {conv.tags.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {conv.tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {nextCursor && (
            <div className="border-t border-zinc-800/60 p-2">
              <button
                onClick={loadMore}
                disabled={loading}
                className="w-full rounded-lg py-2 text-xs text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-40"
              >
                Load more
              </button>
            </div>
          )}
        </div>

        {/* Right thread pane */}
        <div
          data-testid="conversations-thread-pane"
          className={`flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/40 ${
            selected ? "flex min-h-0 w-full" : "hidden min-h-0 md:flex"
          }`}
        >
          {selected ? (
            <>
              {/* Thread header */}
              <div className="flex items-center justify-between gap-3 border-b border-zinc-800/60 p-4">
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  <button
                    type="button"
                    aria-label="Back to inbox"
                    data-testid="conversations-mobile-back"
                    className="mt-0.5 shrink-0 rounded-lg p-1 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100 md:hidden"
                    onClick={() => setSelected(null)}
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <UrgencyDot urgency={selected.urgency} />
                    <h2 className="truncate text-sm font-semibold text-zinc-100">
                      {selected.title}
                    </h2>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5 md:pl-4">
                    <StatusBadge status={selected.status} />
                    {selected.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  {selected.status !== "resolved" && (
                    <ActionButton
                      icon={<CheckCircle2 className="h-4 w-4" />}
                      label="Resolve"
                      onClick={() => void handleStatusAction(selected.id, "resolved")}
                    />
                  )}
                  {selected.status === "resolved" && (
                    <ActionButton
                      icon={<RotateCcw className="h-4 w-4" />}
                      label="Re-open"
                      onClick={() => void handleStatusAction(selected.id, "needs-action")}
                    />
                  )}
                  <div className="relative">
                    <ActionButton
                      icon={<BellOff className="h-4 w-4" />}
                      label="Snooze"
                      onClick={() => setSnoozingId(selected.id)}
                    />
                    {snoozingId === selected.id && (
                      <SnoozePicker
                        onSelect={(until) => void handleSnooze(selected.id, until)}
                        onClose={() => setSnoozingId(null)}
                      />
                    )}
                  </div>
                  <ActionButton
                    icon={<Archive className="h-4 w-4" />}
                    label="Archive"
                    onClick={() => void handleStatusAction(selected.id, "archived")}
                  />
                </div>
              </div>

              {selected.links?.expense_id ? (
                <div className="border-b border-zinc-800/60 px-4 pb-2">
                  <ExpenseConversationCard
                    conversationId={selected.id}
                    expenseId={selected.links.expense_id}
                    conversation={selected}
                    onResolved={({ conversation: c }) => {
                      updateSelectedFromList(c);
                    }}
                  />
                </div>
              ) : null}

              {/* Messages */}
              <div className="flex min-h-0 flex-1 flex-col-reverse gap-4 overflow-y-auto p-4">
                {[...selected.messages].reverse().map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))}
              </div>

              {/* Reply box */}
              <div className="border-t border-zinc-800/60 p-4">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Reply… (markdown supported)"
                  rows={3}
                  className="w-full resize-none rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-sky-500/50"
                />
                <div className="mt-2 flex justify-end">
                  <button
                    onClick={() => void handleReply()}
                    disabled={replyLoading || !replyText.trim()}
                    className="rounded-lg bg-sky-500/20 px-4 py-1.5 text-sm font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/30 disabled:opacity-40"
                  >
                    {replyLoading ? "Sending…" : "Send reply"}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-zinc-600">
              Select a conversation to view the thread
            </div>
          )}
        </div>
      </div>

      {showCompose && (
        <ComposeModal
          onClose={() => setShowCompose(false)}
          onSuccess={handleComposeSuccess}
        />
      )}
    </div>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-200"
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function StatusBadge({ status }: { status: StatusLevel }) {
  const classes: Record<StatusLevel, string> = {
    "needs-action": "bg-amber-500/20 text-amber-200",
    open: "bg-sky-500/20 text-sky-200",
    snoozed: "bg-zinc-500/20 text-zinc-400",
    resolved: "bg-emerald-500/20 text-emerald-300",
    archived: "bg-zinc-700/40 text-zinc-500",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${classes[status]}`}>
      {status}
    </span>
  );
}

function EmptyState({ filter, search }: { filter: FilterChip; search: string }) {
  if (search) {
    return (
      <div data-testid="conversations-empty-search" className="p-8 text-center text-sm text-zinc-500">
        Search returned no results for &ldquo;{search}&rdquo;
      </div>
    );
  }
  if (filter === "needs-action") {
    return (
      <div data-testid="conversations-empty-needs-action" className="p-8 text-center">
        <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-emerald-500/60" />
        <p className="text-sm text-zinc-500">
          All caught up — nothing needs your action
        </p>
      </div>
    );
  }
  return (
    <div data-testid="conversations-empty-filter" className="p-8 text-center text-sm text-zinc-500">
      No conversations match this filter
    </div>
  );
}

function PushBadgePill() {
  const [pushOn, setPushOn] = useState(false);
  const count = useUnreadCount();

  useEffect(() => {
    if (!isPushSupported()) return;
    if (Notification.permission === "granted") {
      setPushOn(true);
    }
  }, []);

  if (!pushOn) return null;

  return (
    <span className="flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300 ring-1 ring-emerald-500/30">
      <Bell className="h-3 w-3" />
      Push: On
      {count > 0 && (
        <>
          {" · "}
          <span>Badge: {count}</span>
        </>
      )}
    </span>
  );
}
