"use client";

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
  Bot,
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
  ConversationParticipant,
  ConversationSpace,
  ConversationsListPage,
  FilterChip,
  StatusLevel,
  ThreadMessage,
  UrgencyLevel,
} from "@/types/conversations";
import type { ComposePersonaOption } from "@/lib/compose-persona-options";
import type { EmployeeListItem } from "@/lib/brain-client";
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
import { ComposeModal } from "./compose-modal";
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

const QUICK_REACTION_EMOJIS = ["👍", "❤️", "✅", "👀", "🚀"] as const;

const FOUNDER_PARTICIPANT_ID = "founder";

function rosterBySlugMap(roster: EmployeeListItem[]): Map<string, EmployeeListItem> {
  const m = new Map<string, EmployeeListItem>();
  for (const e of roster) m.set(e.slug, e);
  return m;
}

type ParticipantEnrichment = { avatarEmoji: string | null; displayLabel: string };

function enrichParticipant(
  p: ConversationParticipant,
  bySlug: Map<string, EmployeeListItem>,
): ParticipantEnrichment {
  const fallback = p.display_name ?? p.id;
  if (p.kind !== "persona") {
    return { avatarEmoji: null, displayLabel: fallback };
  }
  const emp = bySlug.get(p.id);
  return {
    avatarEmoji: emp?.avatar_emoji ?? null,
    displayLabel: emp?.display_name ?? fallback,
  };
}

const MENTION_IN_BODY_RE = /@([\w-]+)/g;

function engagedPersonaSlugsForContext(
  messages: ThreadMessage[],
  replyPersonaIds: Set<string>,
  bySlug: Map<string, EmployeeListItem>,
): string[] {
  const slugs = new Set<string>();
  for (const m of messages) {
    if (m.author.kind === "persona") slugs.add(m.author.id);
    let mm: RegExpExecArray | null;
    const re = new RegExp(MENTION_IN_BODY_RE.source, "g");
    while ((mm = re.exec(m.body_md)) !== null) slugs.add(mm[1]!);
  }
  return [...slugs].filter(
    (s) => replyPersonaIds.has(s) || bySlug.get(s)?.kind === "ai_persona",
  );
}

function PersonaContextPanel({
  slugs,
  bySlug,
  personaDispatchBySlug,
  replyPersonas,
}: {
  slugs: string[];
  bySlug: Map<string, EmployeeListItem>;
  personaDispatchBySlug: Record<string, number>;
  replyPersonas: BrainPersonaOption[];
}) {
  if (slugs.length === 0) return null;
  const labelLookup = new Map(replyPersonas.map((p) => [p.id, p.label]));

  return (
    <details
      data-testid="persona-context-panel"
      className="group border-b border-zinc-800/60 bg-zinc-950/35"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2 text-xs font-medium text-zinc-400 transition hover:bg-zinc-900/50 hover:text-zinc-200 [&::-webkit-details-marker]:hidden">
        <ChevronDown className="h-3.5 w-3.5 shrink-0 transition group-open:rotate-180" />
        <Bot className="h-3.5 w-3.5 text-violet-400/90" aria-hidden />
        <span>
          Persona context ({slugs.length}) — mentioned or active in this thread
        </span>
      </summary>
      <div className="space-y-2 border-t border-zinc-800/40 px-4 pb-3 pt-2">
        {slugs.map((slug) => {
          const emp = bySlug.get(slug);
          const recent = personaDispatchBySlug[slug];
          const name = emp?.display_name ?? labelLookup.get(slug) ?? slug;
          return (
            <div
              key={slug}
              className="rounded-lg border border-zinc-800/70 bg-zinc-900/50 px-3 py-2 text-xs text-zinc-300"
            >
              <div className="flex flex-wrap items-center gap-2">
                {emp?.avatar_emoji ? (
                  <span className="text-base" aria-hidden>
                    {emp.avatar_emoji}
                  </span>
                ) : null}
                <span className="font-medium text-zinc-100">{name}</span>
                <span className="rounded-full bg-violet-500/20 px-1.5 py-px text-[10px] font-medium text-violet-300">
                  AI
                </span>
              </div>
              <p className="mt-1 text-[11px] text-zinc-500">
                {emp?.role_title ? (
                  <>
                    <span className="text-zinc-400">{emp.role_title}</span>
                    {emp.team ? " · " : ""}
                  </>
                ) : null}
                {emp?.team ? <span>{emp.team}</span> : null}
                {!emp?.role_title && !emp?.team ? (
                  <span className="font-mono text-zinc-500">@{slug}</span>
                ) : null}
              </p>
              {recent !== undefined ? (
                <p className="mt-1 text-[11px] text-zinc-500">
                  Recent activity (30d): <span className="tabular-nums text-zinc-400">{recent}</span>{" "}
                  dispatches
                </p>
              ) : (
                <p className="mt-1 text-[11px] text-zinc-500">Recent activity: not available</p>
              )}
            </div>
          );
        })}
      </div>
    </details>
  );
}

function getThreadContext(messages: ThreadMessage[], anchorId: string) {
  const byId = new Map(messages.map((m) => [m.id, m]));
  const anchor = byId.get(anchorId);
  if (!anchor) return null;
  const root = anchor.parent_message_id
    ? (byId.get(anchor.parent_message_id) ?? anchor)
    : anchor;
  const replies = messages
    .filter((m) => m.parent_message_id === root.id)
    .slice()
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  return { root, replies };
}

/** Oldest → newest: root message then its direct replies. */
function getOrderedThreadMessages(messages: ThreadMessage[], anchorId: string): ThreadMessage[] | null {
  const ctx = getThreadContext(messages, anchorId);
  if (!ctx) return null;
  return [ctx.root, ...ctx.replies];
}

/**
 * TODO(PB-8): Set to true when Brain implements POST /api/v1/admin/conversations/{id}/reply
 * ({ persona_slug, content }). Verified missing in apis/brain/app/routers/conversations.py (2026-05-01).
 */
const BRAIN_CONVERSATION_PERSONA_REPLY_READY = false;

function ParticipantAvatar({
  participant,
  avatarEmoji,
}: {
  participant: ConversationParticipant;
  avatarEmoji?: string | null;
}) {
  const label = participant.display_name ?? participant.id;
  const initial = label.trim().charAt(0).toUpperCase() || "?";
  if (avatarEmoji) {
    return (
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-lg leading-none"
        aria-hidden
        title={label}
      >
        {avatarEmoji}
      </div>
    );
  }
  return (
    <div
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-700 text-xs font-medium text-zinc-200"
      aria-hidden
    >
      {initial}
    </div>
  );
}

function AiBadge() {
  return (
    <span className="rounded-full bg-violet-500/20 px-1.5 py-px text-[10px] font-medium text-violet-300">
      AI
    </span>
  );
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

function MessageBubble({
  msg,
  enrichment,
}: {
  msg: ThreadMessage;
  enrichment: ParticipantEnrichment;
}) {
  const isPersona = msg.author.kind === "persona";
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        {enrichment.avatarEmoji ? (
          <span className="text-sm" aria-hidden>
            {enrichment.avatarEmoji}
          </span>
        ) : null}
        <span className="text-xs font-medium text-zinc-300">{enrichment.displayLabel}</span>
        {isPersona ? <AiBadge /> : null}
        <span className="text-[10px] text-zinc-600">
          {new Date(msg.created_at).toLocaleString()}
        </span>
      </div>
      <div
        className={`rounded-xl border px-4 py-3 ${
          isPersona
            ? "border-zinc-800/80 border-l-2 border-l-violet-500/30 bg-zinc-900/60"
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

function ThreadPanelMessageRow({
  msg,
  isAnchor,
  isPending,
  enrichment,
}: {
  msg: ThreadMessage;
  isAnchor: boolean;
  isPending?: boolean;
  enrichment: ParticipantEnrichment;
}) {
  const isPersona = msg.author.kind === "persona";
  return (
    <div
      data-testid={`thread-panel-message-${msg.id}`}
      className={`rounded-xl border px-3 py-2 ${
        isAnchor
          ? "border-sky-500/50 bg-sky-950/30 ring-1 ring-sky-500/30"
          : isPersona
            ? "border-zinc-800/80 border-l-2 border-l-violet-500/30 bg-zinc-900/60"
            : "border-zinc-800/80 bg-zinc-900/40"
      } ${isPending ? "opacity-85" : ""}`}
    >
      <div className="flex gap-3">
        <ParticipantAvatar participant={msg.author} avatarEmoji={enrichment.avatarEmoji} />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-zinc-200">{enrichment.displayLabel}</span>
            {isPersona ? <AiBadge /> : null}
            <span className="text-[10px] text-zinc-500">
              {new Date(msg.created_at).toLocaleString()}
            </span>
            {isPending ? (
              <span className="text-[10px] font-medium text-amber-300/90">Sending…</span>
            ) : null}
          </div>
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
  /** Brain `/admin/employees` — enriches persona avatars + context sidebar. */
  employeeRoster?: EmployeeListItem[];
  /** From `getPersonaDispatchSummary()` keyed by `persona_slug`. */
  personaDispatchBySlug?: Record<string, number>;
}

export function ConversationsClient({
  brainConfigured,
  initialPage,
  setupError = null,
  setupWarning = null,
  composePersonaOptions = [],
  replyPersonas = [],
  employeeRoster = [],
  personaDispatchBySlug = {},
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
  const [composerError, setComposerError] = useState<string | null>(null);
  const [threadAnchorId, setThreadAnchorId] = useState<string | null>(null);
  const [composeInitialPersonaSlug, setComposeInitialPersonaSlug] = useState<string | null>(null);
  const [threadReplyText, setThreadReplyText] = useState("");
  const [threadReplyPersonaSlug, setThreadReplyPersonaSlug] = useState("");
  const [threadReplyLoading, setThreadReplyLoading] = useState(false);
  const [threadReplyError, setThreadReplyError] = useState<string | null>(null);
  const [threadOptimisticMessages, setThreadOptimisticMessages] = useState<ThreadMessage[]>([]);
  const [spaceFilter, setSpaceFilter] = useState<ConversationSpace | "all">("all");
  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [requestReplySlug, setRequestReplySlug] = useState("");
  const [requestReplyLoading, setRequestReplyLoading] = useState(false);
  const [requestReplyNotice, setRequestReplyNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  const employeeBySlug = useMemo(() => rosterBySlugMap(employeeRoster), [employeeRoster]);
  const replyPersonaIdSet = useMemo(
    () => new Set(replyPersonas.map((p) => p.id)),
    [replyPersonas],
  );
  const contextPersonaSlugs = useMemo(() => {
    if (!selected) return [];
    return engagedPersonaSlugsForContext(
      selected.messages,
      replyPersonaIdSet,
      employeeBySlug,
    );
  }, [selected, replyPersonaIdSet, employeeBySlug]);

  useEffect(() => {
    const compose = searchParams.get("compose");
    const openCompose = compose === "true" || compose === "1";
    if (!openCompose) return;
    const slug = searchParams.get("persona")?.trim() ?? null;
    setComposeInitialPersonaSlug(slug && slug.length > 0 ? slug : null);
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

  const mergeMessageIntoConversation = useCallback((conversationId: string, updatedMsg: ThreadMessage) => {
    const patch = (c: Conversation): Conversation =>
      c.id !== conversationId
        ? c
        : {
            ...c,
            messages: c.messages.map((m) => (m.id === updatedMsg.id ? updatedMsg : m)),
            updated_at: new Date().toISOString(),
          };
    setConversations((prev) => prev.map(patch));
    setSelected((s) => (s?.id === conversationId ? patch(s) : s));
  }, []);

  const threadCtx = useMemo(() => {
    if (!selected || !threadAnchorId) return null;
    return getThreadContext(selected.messages, threadAnchorId);
  }, [selected, threadAnchorId]);

  const threadOrderedMessages = useMemo(() => {
    if (!selected || !threadAnchorId) return null;
    return getOrderedThreadMessages(selected.messages, threadAnchorId);
  }, [selected, threadAnchorId]);

  useEffect(() => {
    setThreadAnchorId(null);
    setThreadOptimisticMessages([]);
    setThreadReplyError(null);
    setThreadReplyText("");
    setThreadReplyPersonaSlug("");
    setRequestReplySlug("");
    setRequestReplyLoading(false);
    setRequestReplyNotice(null);
  }, [selected?.id]);

  useEffect(() => {
    setThreadOptimisticMessages([]);
    setThreadReplyError(null);
  }, [threadAnchorId]);

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
    [selected],
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

  const handleThreadPanelReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!BRAIN_CONVERSATION_PERSONA_REPLY_READY) return;
    if (!selected || !threadAnchorId || !threadReplyPersonaSlug || !threadReplyText.trim()) return;
    const trimmed = threadReplyText.trim();
    const personaMeta = replyPersonas.find((p) => p.id === threadReplyPersonaSlug);
    const rootId = threadCtx?.root.id;
    const optimistic: ThreadMessage = {
      id: `pending-${crypto.randomUUID()}`,
      author: {
        id: threadReplyPersonaSlug,
        kind: "persona",
        display_name: personaMeta?.label ?? threadReplyPersonaSlug,
      },
      body_md: trimmed,
      attachments: [],
      created_at: new Date().toISOString(),
      reactions: {},
      parent_message_id: rootId ?? null,
    };

    setThreadReplyLoading(true);
    setThreadReplyError(null);
    setThreadOptimisticMessages((prev) => [...prev, optimistic]);
    setThreadReplyText("");

    try {
      const res = await fetch(`/api/admin/conversations/${selected.id}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          persona_slug: threadReplyPersonaSlug,
          content: trimmed,
        }),
      });
      const json: { success?: boolean; error?: string } = await res.json().catch(() => ({}));
      if (!res.ok || !json.success) {
        setThreadOptimisticMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
        setThreadReplyError(json.error ?? `Reply failed (${res.status})`);
        return;
      }
      setThreadOptimisticMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
      if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
    } catch (err) {
      setThreadOptimisticMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setThreadReplyError(err instanceof Error ? err.message : "Unexpected error sending reply");
    } finally {
      setThreadReplyLoading(false);
    }
  };

  const handleRequestPersonaReply = async () => {
    if (!selected || !requestReplySlug.trim()) return;
    const slug = requestReplySlug.trim();
    setRequestReplyLoading(true);
    setRequestReplyNotice(null);
    try {
      const res = await fetch(`/api/admin/conversations/${selected.id}/request-reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_slug: slug }),
      });
      const json: {
        success?: boolean;
        error?: string;
        message?: string;
        data?: { message?: string };
      } | null = await res.json().catch(() => null);
      if (!res.ok) {
        const errText =
          json !== null && typeof json.error === "string" && json.error
            ? json.error
            : `Request failed (${res.status})`;
        setRequestReplyNotice({ kind: "error", text: errText });
        return;
      }
      if (json !== null && json.success === false) {
        setRequestReplyNotice({
          kind: "error",
          text: json.error ?? "Request failed",
        });
        return;
      }
      const dataMsg =
        json !== null &&
        json.data &&
        typeof json.data === "object" &&
        typeof json.data.message === "string"
          ? json.data.message
          : undefined;
      const msg =
        json !== null && typeof json.message === "string"
          ? json.message
          : dataMsg ?? "Persona reply requested.";
      setRequestReplyNotice({ kind: "success", text: msg });
      const convJson = await apiFetch(`/api/admin/conversations/${selected.id}`);
      if (convJson.success && convJson.data) updateSelectedFromList(convJson.data);
    } catch (err) {
      setRequestReplyNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setRequestReplyLoading(false);
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


  const handleReaction = async (msgId: string, emoji: string) => {
    if (!selected) return;
    const json = await apiFetch(`/api/admin/conversations/${selected.id}/messages/${msgId}/react`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emoji, participant_id: FOUNDER_PARTICIPANT_ID }),
    });
    if (json.success && json.data) {
      mergeMessageIntoConversation(selected.id, json.data as ThreadMessage);
    }
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
                      onClick={() => setSelected(conv)}
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
              <div className="flex items-start justify-between gap-3 border-b border-zinc-800/60 p-4">
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
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  {requestReplyLoading ? (
                    <p
                      data-testid="request-persona-reply-loading"
                      className="max-w-[14rem] text-right text-[11px] text-violet-300/90"
                    >
                      Requesting reply from @{requestReplySlug}…
                    </p>
                  ) : null}
                  {requestReplyNotice && !requestReplyLoading ? (
                    <p
                      data-testid={
                        requestReplyNotice.kind === "error"
                          ? "request-persona-reply-error"
                          : "request-persona-reply-success"
                      }
                      className={`max-w-[14rem] text-right text-[11px] ${
                        requestReplyNotice.kind === "error" ? "text-red-400" : "text-emerald-400"
                      }`}
                    >
                      {requestReplyNotice.text}
                    </p>
                  ) : null}
                  <div
                    className="flex flex-wrap items-center justify-end gap-1.5"
                    data-testid="request-persona-reply-controls"
                  >
                    <label className="flex items-center gap-1 text-[10px] text-zinc-500">
                      <Bot className="h-3 w-3 text-violet-400/80" aria-hidden />
                      <span className="sr-only">Persona for reply request</span>
                      <select
                        value={requestReplySlug}
                        onChange={(e) => {
                          setRequestReplySlug(e.target.value);
                          setRequestReplyNotice(null);
                        }}
                        disabled={requestReplyLoading || replyPersonas.length === 0}
                        className="max-w-[9rem] rounded-lg border border-zinc-800 bg-zinc-900 py-1 pl-2 pr-6 text-[11px] text-zinc-200 outline-none focus:border-violet-500/40 disabled:opacity-40"
                      >
                        <option value="">Request reply as…</option>
                        {replyPersonas.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      data-testid="request-persona-reply-submit"
                      disabled={requestReplyLoading || !requestReplySlug || replyPersonas.length === 0}
                      onClick={() => void handleRequestPersonaReply()}
                      className="flex items-center gap-1 rounded-lg bg-violet-500/15 px-2 py-1.5 text-[11px] font-medium text-violet-200 ring-1 ring-violet-500/35 transition hover:bg-violet-500/25 disabled:opacity-40"
                    >
                      {requestReplyLoading ? (
                        <>Requesting…</>
                      ) : (
                        <>
                          <Bot className="h-3.5 w-3.5" aria-hidden />
                          <span className="hidden sm:inline">Request reply</span>
                          <span className="sm:hidden">Request</span>
                        </>
                      )}
                    </button>
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

              <PersonaContextPanel
                slugs={contextPersonaSlugs}
                bySlug={employeeBySlug}
                personaDispatchBySlug={personaDispatchBySlug}
                replyPersonas={replyPersonas}
              />

              {/* Messages + optional thread sub-panel */}
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
                <div className="flex min-h-[200px] flex-1 flex-col md:min-h-0">
                  <div className="flex min-h-0 flex-1 flex-col-reverse gap-4 overflow-y-auto p-4">
                    {[...selected.messages].reverse().map((msg) => (
                      <button
                        key={msg.id}
                        type="button"
                        data-testid={`conversation-message-${msg.id}`}
                        className={`w-full rounded-lg text-left outline-none ring-offset-2 ring-offset-zinc-900 transition hover:bg-zinc-800/30 focus-visible:ring-2 focus-visible:ring-sky-500/50 ${
                          threadAnchorId === msg.id ? "bg-zinc-800/40 ring-1 ring-sky-500/30" : ""
                        }`}
                        onClick={() => setThreadAnchorId(msg.id)}
                      >
                        <MessageBubble
                          msg={msg}
                          enrichment={enrichParticipant(msg.author, employeeBySlug)}
                        />
                      </button>
                    ))}
                  </div>
                </div>

                {threadAnchorId && threadOrderedMessages ? (
                  <div
                    data-testid="conversation-thread-subpanel"
                    className="flex max-h-[50vh] w-full shrink-0 flex-col border-t border-zinc-800/80 bg-zinc-950/40 md:max-h-none md:h-auto md:w-[min(100%,22rem)] md:border-l md:border-t-0"
                  >
                    <div className="flex items-center justify-between border-b border-zinc-800/60 px-3 py-2">
                      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Thread
                      </p>
                      <button
                        type="button"
                        aria-label="Close thread panel"
                        className="rounded p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-200"
                        onClick={() => setThreadAnchorId(null)}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
                      {threadOrderedMessages.map((msg) => (
                        <ThreadPanelMessageRow
                          key={msg.id}
                          msg={msg}
                          isAnchor={msg.id === threadAnchorId}
                          enrichment={enrichParticipant(msg.author, employeeBySlug)}
                        />
                      ))}
                      {threadOptimisticMessages.map((msg) => (
                        <ThreadPanelMessageRow
                          key={msg.id}
                          msg={msg}
                          isAnchor={false}
                          isPending={msg.id.startsWith("pending-")}
                          enrichment={enrichParticipant(msg.author, employeeBySlug)}
                        />
                      ))}
                    </div>
                    <form
                      data-testid="thread-panel-reply-form"
                      className="border-t border-zinc-800/60 p-3"
                      onSubmit={(e) => void handleThreadPanelReply(e)}
                    >
                      {threadReplyError ? (
                        <p className="mb-2 text-xs text-red-400">{threadReplyError}</p>
                      ) : null}
                      <label htmlFor="thread-reply-persona" className="mb-1 block text-xs font-medium text-zinc-500">
                        Reply as
                      </label>
                      <select
                        id="thread-reply-persona"
                        data-testid="thread-panel-reply-persona"
                        value={threadReplyPersonaSlug}
                        onChange={(e) => setThreadReplyPersonaSlug(e.target.value)}
                        className="mb-2 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-200 outline-none focus:border-sky-500/50"
                      >
                        <option value="">Select persona…</option>
                        {replyPersonas.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                      <div className="mb-2">
                        <ConversationComposer
                          value={threadReplyText}
                          onChange={setThreadReplyText}
                          slashCommands={slashCommandsRegistry}
                          personas={replyPersonas}
                          disabled={
                            threadReplyLoading || !BRAIN_CONVERSATION_PERSONA_REPLY_READY
                          }
                          placeholder="Write your reply..."
                          textareaTestId="thread-panel-reply-text"
                        />
                      </div>
                      <button
                        type="submit"
                        data-testid="thread-panel-reply-send"
                        disabled={
                          threadReplyLoading ||
                          !BRAIN_CONVERSATION_PERSONA_REPLY_READY ||
                          !threadReplyPersonaSlug ||
                          !threadReplyText.trim()
                        }
                        title={
                          BRAIN_CONVERSATION_PERSONA_REPLY_READY
                            ? undefined
                            : "Reply backend not yet wired (PB-X)"
                        }
                        className="rounded-lg bg-sky-500/20 px-3 py-1.5 text-sm font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/30 disabled:opacity-40"
                      >
                        {threadReplyLoading ? "Sending…" : "Send"}
                      </button>
                    </form>
                  </div>
                ) : null}
              </div>

              {/* Reply box */}
              <div className="border-t border-zinc-800/60 p-4">
                {composerError ? (
                  <p
                    className="mb-2 text-sm text-red-400"
                    data-testid="conversation-composer-error"
                  >
                    {composerError}
                  </p>
                ) : null}
                <ConversationComposer
                  value={replyText}
                  onChange={(v) => {
                    setReplyText(v);
                    setComposerError(null);
                  }}
                  slashCommands={slashCommandsRegistry}
                  personas={replyPersonas}
                  disabled={replyLoading}
                  placeholder="Reply… (markdown supported)"
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
          personaOptions={composePersonaOptions}
          initialPersonaSlug={composeInitialPersonaSlug}
          onClose={() => {
            setShowCompose(false);
            setComposeInitialPersonaSlug(null);
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
