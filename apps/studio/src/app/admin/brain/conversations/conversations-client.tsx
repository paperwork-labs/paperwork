"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Archive,
  Bell,
  BellOff,
  BookMarked,
  Building2,
  ChartColumnBig,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  FileText,
  Layers,
  MessageSquare,
  Paperclip,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  TriangleAlert,
  User,
  X,
} from "lucide-react";
import type {
  Conversation,
  ConversationSpace,
  ConversationsListPage,
  FilterChip,
  StatusLevel,
  ThreadMessage,
  UrgencyLevel,
} from "@/types/conversations";
import type { ComposePersonaOption } from "@/lib/compose-persona-options";
import {
  CONVERSATION_SPACES,
  effectiveConversationSpace,
  type SpaceGlyphId,
  spaceDisplayName,
} from "@/lib/conversation-spaces";
import { AppBadgeManager, useUnreadCount } from "@/components/pwa/AppBadgeManager";
import { isPushSupported } from "@/lib/web-push";
import { ExpenseConversationCard } from "@/components/admin/ExpenseConversationCard";
import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqErrorState } from "@/components/admin/hq/HqErrorState";
import { HqMissingCredCard } from "@/components/admin/hq/HqMissingCredCard";
import { ComposeModal, type ComposeModalPrefill } from "./compose-modal";
import {
  createSlashCommands,
  runSlashPrefixedLine,
  SlashCommandValidationError,
} from "@/lib/slash-commands";
import { ConversationComposer } from "./conversation-composer";
import type { BrainPersonaOption } from "./conversation-composer";
import { SnoozePicker } from "./snooze-picker";

function prependPersonaRoutingLine(body: string): string {
  const mentions = Array.from(body.matchAll(/@([\w-]+)/g)).map((m) => m[1]);
  if (mentions.length === 0) return body;
  const unique = [...new Set(mentions)].map((m) => `\`@${m}\``).join(", ");
  return `**Route to persona:** ${unique}\n\n${body}`;
}

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

const SPACE_GLYPH_ICONS: Record<SpaceGlyphId, LucideIcon> = {
  user: User,
  building: Building2,
  chart: ChartColumnBig,
  file: FileText,
  book: BookMarked,
  alert: TriangleAlert,
};

function SpaceFilterChip({
  testId,
  label,
  icon: Icon,
  active,
  onClick,
  badge,
}: {
  testId: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  onClick: () => void;
  badge: number;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      title={label}
      onClick={onClick}
      className={`flex min-w-0 max-w-[9rem] items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-xs transition ${
        active
          ? "bg-sky-500/20 text-sky-200 ring-1 ring-sky-500/40"
          : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
      }`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {badge > 0 ? (
        <span className="shrink-0 rounded-full bg-zinc-700 px-1 py-0.5 text-[10px] tabular-nums text-zinc-200">
          {badge}
        </span>
      ) : null}
    </button>
  );
}

/**
 * TODO(PB-X): Brain POST `/admin/conversations/{id}/reply` with `{ persona_slug, content }`; enable when wired.
 */
const ADMIN_CONVERSATION_REPLY_WIRED = false;

function authorInitials(name: string | null | undefined, id: string): string {
  const n = (name ?? "").trim();
  if (n.length > 0) {
    const parts = n.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]![0]!}${parts[1]![0]!}`.toUpperCase();
    }
    return parts[0]!.slice(0, 2).toUpperCase();
  }
  return id.slice(0, 2).toUpperCase();
}

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

function MessageBubble({ msg, highlighted }: { msg: ThreadMessage; highlighted?: boolean }) {
  const label = msg.author.display_name ?? msg.author.id;
  const initials = authorInitials(msg.author.display_name, msg.author.id);
  return (
    <div className="space-y-1" data-msg-id={msg.id}>
      <div className="flex items-center gap-2">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-[11px] font-semibold uppercase text-zinc-200 ring-1 ring-zinc-700"
          aria-hidden
        >
          {initials}
        </span>
        <span className="text-xs font-medium text-zinc-300">{label}</span>
        <span className="text-[10px] text-zinc-600">
          {new Date(msg.created_at).toLocaleString()}
        </span>
      </div>
      <div
        className={`rounded-xl border px-4 py-3 ${
          highlighted
            ? "border-sky-500/50 bg-sky-950/30 ring-1 ring-sky-500/35"
            : "border-zinc-800/80 bg-zinc-900/60"
        }`}
      >
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
  /** Inbox load failed server-side — full-page error. */
  setupError?: string | null;
  /** Disk / backfill issues — inline banner only; inbox still loads. */
  setupWarning?: string | null;
  composePersonaOptions?: ComposePersonaOption[];
  replyPersonas?: BrainPersonaOption[];
}

export function ConversationsClient({
  brainConfigured,
  initialPage,
  setupError = null,
  setupWarning = null,
  composePersonaOptions = [],
  replyPersonas = [],
}: Props) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const composeParam = searchParams.get("compose") ?? "";
  const composePersonaParam = searchParams.get("persona") ?? "";

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
  const [composerError, setComposerError] = useState<string | null>(null);
  const [threadAnchorId, setThreadAnchorId] = useState<string | null>(null);
  const [composePrefill, setComposePrefill] = useState<ComposeModalPrefill | null>(null);
  const [threadReplyPersonaSlug, setThreadReplyPersonaSlug] = useState(
    () => replyPersonas[0]?.id ?? "",
  );
  const [threadPersonaReplyText, setThreadPersonaReplyText] = useState("");
  const [threadPersonaReplyError, setThreadPersonaReplyError] = useState<string | null>(null);
  const [threadOptimisticSending, setThreadOptimisticSending] = useState(false);
  const [spaceFilter, setSpaceFilter] = useState<ConversationSpace | "all">("all");
  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const threadScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (replyPersonas.length === 0) return;
    setThreadReplyPersonaSlug((prev) => {
      if (replyPersonas.some((p) => p.id === prev)) return prev;
      return replyPersonas[0]!.id;
    });
  }, [replyPersonas]);

  useEffect(() => {
    const openCompose = composeParam === "true" || composeParam === "1";
    if (!openCompose) return;
    setShowCompose(true);
    const slug = composePersonaParam.trim();
    setComposePrefill(slug ? { personaSlug: slug } : null);
    router.replace(pathname, { scroll: false });
  }, [composeParam, composePersonaParam, router, pathname]);

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

  const updateSelectedFromList = useCallback((updated: Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    setSelected((s) => (s?.id === updated.id ? updated : s));
  }, []);

  const appendPersonaMessageOptimistic = useCallback((conversationId: string, msg: ThreadMessage) => {
    const patch = (c: Conversation): Conversation =>
      c.id !== conversationId
        ? c
        : {
            ...c,
            messages: [...c.messages, msg],
            updated_at: new Date().toISOString(),
          };
    setConversations((prev) => prev.map(patch));
    setSelected((s) => (s?.id === conversationId ? patch(s) : s));
  }, []);

  const removeMessageById = useCallback((conversationId: string, messageId: string) => {
    const patch = (c: Conversation): Conversation =>
      c.id !== conversationId
        ? c
        : {
            ...c,
            messages: c.messages.filter((m) => m.id !== messageId),
            updated_at: new Date().toISOString(),
          };
    setConversations((prev) => prev.map(patch));
    setSelected((s) => (s?.id === conversationId ? patch(s) : s));
  }, []);

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

  const emitThreadMarkdown = useCallback(
    async (bodyMd: string): Promise<void> => {
      if (!selected) return;
      const json = await apiFetch(`/api/admin/conversations/${selected.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: { id: "founder", kind: "founder", display_name: "Founder" },
          body_md: bodyMd,
          attachments: [],
        }),
      });
      if (!json.success) {
        throw new SlashCommandValidationError(json.error ?? "Failed to post message");
      }
      const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
      if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
    },
    [selected, updateSelectedFromList],
  );

  const slashCommandsRegistry = useMemo(() => {
    if (!selected) return [];
    return createSlashCommands({
      conversationId: selected.id,
      emitMessage: emitThreadMarkdown,
    });
  }, [selected, emitThreadMarkdown]);

  const handleReply = async () => {
    if (!selected || !replyText.trim()) return;
    setReplyLoading(true);
    setComposerError(null);
    try {
      const trimmed = replyText.trim();
      const slashOutcome = await runSlashPrefixedLine(trimmed, slashCommandsRegistry);
      if (slashOutcome.status === "validation_failed") {
        setComposerError(slashOutcome.message);
        return;
      }
      if (slashOutcome.status === "completed") {
        setReplyText("");
        return;
      }

      const plainBody = prependPersonaRoutingLine(trimmed);
      const json = await apiFetch(`/api/admin/conversations/${selected.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author: { id: "founder", kind: "founder", display_name: "Founder" },
          body_md: plainBody,
          attachments: [],
        }),
      });
      if (!json.success) {
        setComposerError(json.error ?? "Unknown error posting reply");
        return;
      }
      setReplyText("");
      const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
      if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
    } catch (e) {
      if (e instanceof SlashCommandValidationError) {
        setComposerError(e.message);
      } else {
        setComposerError(e instanceof Error ? e.message : "Unexpected error sending reply");
      }
    } finally {
      setReplyLoading(false);
    }
  };

  const handleThreadPersonaReply = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setThreadPersonaReplyError(null);
    if (!ADMIN_CONVERSATION_REPLY_WIRED || !selected) return;
    const personaSlug = threadReplyPersonaSlug.trim();
    const content = threadPersonaReplyText.trim();
    if (!personaSlug || !content) return;
    const opt = replyPersonas.find((p) => p.id === personaSlug);
    const displayName = opt?.label ?? personaSlug;
    const tempId = `pending-reply-${crypto.randomUUID()}`;
    const nowIso = new Date().toISOString();
    const optimistic: ThreadMessage = {
      id: tempId,
      author: { id: personaSlug, kind: "persona", display_name: displayName },
      body_md: content,
      attachments: [],
      created_at: nowIso,
      reactions: {},
    };
    appendPersonaMessageOptimistic(selected.id, optimistic);
    setThreadAnchorId(tempId);
    setThreadPersonaReplyText("");
    setThreadOptimisticSending(true);
    try {
      const json = await apiFetch(`/api/admin/conversations/${selected.id}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_slug: personaSlug, content }),
      });
      if (!json.success) {
        removeMessageById(selected.id, tempId);
        setThreadPersonaReplyError(json.error ?? "Failed to send reply");
        setThreadPersonaReplyText(content);
        setThreadOptimisticSending(false);
        return;
      }
      const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
      if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
    } catch (err) {
      removeMessageById(selected.id, tempId);
      setThreadPersonaReplyError(err instanceof Error ? err.message : "Network error");
      setThreadPersonaReplyText(content);
    } finally {
      setThreadOptimisticSending(false);
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
    const ordered = [...conv.messages].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    setThreadAnchorId(ordered[ordered.length - 1]?.id ?? null);
    setShowCompose(false);
    setComposePrefill(null);
  };


  const displayedConversations = useMemo(() => {
    if (spaceFilter === "all") return conversations;
    return conversations.filter((c) => effectiveConversationSpace(c) === spaceFilter);
  }, [conversations, spaceFilter]);

  const spaceUnreadCounts = useMemo(() => {
    const bySpace: Partial<Record<ConversationSpace, number>> = {};
    let all = 0;
    for (const c of conversations) {
      if (c.needs_founder_action === false) continue;
      all++;
      const sp = effectiveConversationSpace(c);
      bySpace[sp] = (bySpace[sp] ?? 0) + 1;
    }
    return { all, bySpace };
  }, [conversations]);

  const chronologicalMessages = useMemo(() => {
    if (!selected) return [];
    return [...selected.messages].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
  }, [selected]);

  useEffect(() => {
    if (!brainConfigured || !selected?.id) return;
    let cancelled = false;
    void (async () => {
      try {
        const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
        if (cancelled || !convJson.success || !convJson.data) return;
        updateSelectedFromList(convJson.data as Conversation);
      } catch {
        /* keep list-derived conversation */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [brainConfigured, selected?.id, updateSelectedFromList]);

  useEffect(() => {
    if (!threadAnchorId || !threadScrollRef.current) return;
    const node = threadScrollRef.current.querySelector(
      `[data-msg-id="${threadAnchorId}"]`,
    );
    node?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [threadAnchorId, selected?.id, chronologicalMessages.length]);

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

      {setupWarning ? (
        <div
          role="status"
          data-testid="conversations-setup-warning"
          className="rounded-lg border border-amber-800/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-100/90"
        >
          {setupWarning}
        </div>
      ) : null}

      {/* 2-pane layout — single pane on small screens */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row">
        {/* Left inbox */}
        <div
          className={`flex min-h-0 flex-col overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/40 md:w-80 md:shrink-0 ${
            selected ? "hidden min-h-0 md:flex" : "flex w-full min-h-0 flex-1"
          }`}
        >
          <div className="shrink-0 space-y-1 border-b border-zinc-800/60 p-2">
            <p className="px-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
              Channel
            </p>
            <div className="flex flex-wrap gap-1">
              <SpaceFilterChip
                testId="conversation-space-filter-all"
                label="All"
                icon={Layers}
                active={spaceFilter === "all"}
                onClick={() => setSpaceFilter("all")}
                badge={spaceUnreadCounts.all}
              />
              {CONVERSATION_SPACES.map((s) => {
                const Icon = SPACE_GLYPH_ICONS[s.icon];
                return (
                  <SpaceFilterChip
                    key={s.id}
                    testId={`conversation-space-filter-${s.id}`}
                    label={s.name}
                    icon={Icon}
                    active={spaceFilter === s.id}
                    onClick={() => setSpaceFilter(s.id)}
                    badge={spaceUnreadCounts.bySpace[s.id] ?? 0}
                  />
                );
              })}
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading && conversations.length === 0 ? (
              <div data-testid="conversations-loading" className="p-6 text-center text-sm text-zinc-500">
                Loading…
              </div>
            ) : conversations.length === 0 ? (
              <EmptyState filter={activeFilter} search={debouncedSearch} />
            ) : displayedConversations.length === 0 ? (
              <div className="p-4">
                <HqEmptyState
                  title="No conversations in this channel"
                  description="Pick another space or choose All."
                />
              </div>
            ) : (
              <ul role="list" data-testid="conversations-inbox-list" className="divide-y divide-zinc-800/60">
                {displayedConversations.map((conv) => (
                  <li key={conv.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(conv);
                        const ordered = [...conv.messages].sort(
                          (a, b) =>
                            new Date(a.created_at).getTime() -
                            new Date(b.created_at).getTime(),
                        );
                        const lastId = ordered[ordered.length - 1]?.id ?? null;
                        setThreadAnchorId(lastId);
                      }}
                      className={`flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-zinc-800/50 ${
                        selected?.id === conv.id ? "bg-zinc-800/70" : ""
                      }`}
                    >
                      <UrgencyDot urgency={conv.urgency} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-zinc-100">{conv.title}</p>
                        <p className="mt-0.5 truncate text-xs text-zinc-500">
                          {new Date(conv.updated_at).toLocaleDateString()}
                          {conv.persona ? ` · ${conv.persona}` : ""}
                          {" · "}
                          <span className="text-zinc-600">{spaceDisplayName(effectiveConversationSpace(conv))}</span>
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
                    onClick={() => {
                      setSelected(null);
                      setThreadAnchorId(null);
                    }}
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
                    <span
                      data-testid="conversation-detail-space"
                      className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-medium text-violet-200 ring-1 ring-violet-500/30"
                    >
                      {spaceDisplayName(effectiveConversationSpace(selected))}
                    </span>
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

              <div
                ref={threadScrollRef}
                data-testid="conversations-thread-subpanel"
                className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4"
              >
                <div className="flex flex-col gap-4">
                  {chronologicalMessages.map((msg) => (
                    <MessageBubble
                      key={msg.id}
                      msg={msg}
                      highlighted={Boolean(threadAnchorId) && msg.id === threadAnchorId}
                    />
                  ))}
                </div>
              </div>

              <div className="shrink-0 space-y-4 border-t border-zinc-800/60 p-4">
                <form
                  data-testid="conversations-persona-reply-form"
                  onSubmit={(e) => void handleThreadPersonaReply(e)}
                  className="space-y-2"
                >
                  <label className="block text-xs font-medium text-zinc-500">
                    Persona
                    <select
                      value={threadReplyPersonaSlug}
                      onChange={(e) => setThreadReplyPersonaSlug(e.target.value)}
                      disabled={replyPersonas.length === 0}
                      className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500/50 disabled:opacity-50"
                      aria-label="Persona"
                    >
                      {replyPersonas.length === 0 ? (
                        <option value="">No personas configured</option>
                      ) : (
                        replyPersonas.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))
                      )}
                    </select>
                  </label>
                  <textarea
                    value={threadPersonaReplyText}
                    onChange={(e) => setThreadPersonaReplyText(e.target.value)}
                    placeholder="Write your reply…"
                    rows={3}
                    className="w-full resize-none rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-sky-500/50"
                  />
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={
                        !ADMIN_CONVERSATION_REPLY_WIRED ||
                        threadOptimisticSending ||
                        !threadPersonaReplyText.trim() ||
                        replyPersonas.length === 0
                      }
                      title={
                        !ADMIN_CONVERSATION_REPLY_WIRED
                          ? "Reply backend not yet wired (PB-X)"
                          : undefined
                      }
                      className="rounded-lg bg-violet-500/20 px-4 py-1.5 text-sm font-medium text-violet-200 ring-1 ring-violet-500/35 transition hover:bg-violet-500/30 disabled:opacity-40"
                    >
                      {threadOptimisticSending ? "Sending…" : "Send"}
                    </button>
                  </div>
                  {threadPersonaReplyError ? (
                    <p
                      role="alert"
                      className="text-sm text-red-300"
                      data-testid="conversations-persona-reply-error"
                    >
                      {threadPersonaReplyError}
                    </p>
                  ) : null}
                </form>

                <div className="border-t border-zinc-800/60 pt-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Founder
                  </p>
                  <ConversationComposer
                    value={replyText}
                    onChange={setReplyText}
                    slashCommands={slashCommandsRegistry}
                    personas={replyPersonas}
                    disabled={replyLoading}
                    placeholder="Reply… (markdown, slash commands, @mentions)"
                  />
                  {composerError ? (
                    <p className="mt-2 text-sm text-red-300">{composerError}</p>
                  ) : null}
                  <div className="mt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() => void handleReply()}
                      disabled={replyLoading || !replyText.trim()}
                      className="rounded-lg bg-sky-500/20 px-4 py-1.5 text-sm font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/30 disabled:opacity-40"
                    >
                      {replyLoading ? "Sending…" : "Send reply"}
                    </button>
                  </div>
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
          personaOptions={composePersonaOptions}
          prefill={composePrefill}
          onClose={() => {
            setShowCompose(false);
            setComposePrefill(null);
          }}
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
