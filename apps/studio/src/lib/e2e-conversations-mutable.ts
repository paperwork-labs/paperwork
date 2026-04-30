import type {
  Attachment,
  Conversation,
  ConversationParticipant,
  ConversationSpace,
  ConversationsListPage,
  StatusLevel,
  ThreadMessage,
  UrgencyLevel,
} from "@/types/conversations";

import { getE2EConversationsListPage } from "@/lib/e2e-conversations-fixture";

const SPACE_ROTATION: ConversationSpace[] = [
  "personal",
  "paperwork-labs",
  "axiomfolio",
  "filefree",
  "runbook-asks",
  "incidents",
];

const SPACE_IDS = new Set<ConversationSpace>(SPACE_ROTATION);

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/** In-memory conversations keyed by id; seeded from founder-actions fixture. */
let store: Map<string, Conversation> | null = null;

function ensureStore(): Map<string, Conversation> {
  if (!store) {
    const page = getE2EConversationsListPage();
    store = new Map(
      page.items.map((c, i) => {
        const clone = deepClone(c);
        clone.space = SPACE_ROTATION[i % SPACE_ROTATION.length];
        return [clone.id, clone];
      }),
    );
  }
  return store;
}

export function resetE2EMutableConversations(): void {
  store = null;
}

export function getE2EMutableListPage(): ConversationsListPage {
  const items = [...ensureStore().values()];
  return { items, next_cursor: null, total: items.length };
}

export function getE2EMutableConversation(id: string): Conversation | null {
  const c = ensureStore().get(id);
  return c ? deepClone(c) : null;
}

export function getE2EMutableConversationsBadge(): { count: number; hasCritical: boolean } {
  const page = getE2EMutableListPage();
  const needs = page.items.filter((c) => c.needs_founder_action !== false);
  return {
    count: needs.length,
    hasCritical: needs.some((c) => c.urgency === "critical"),
  };
}

export function e2eToggleReactionOnMessage(
  conversationId: string,
  messageId: string,
  emoji: string,
  participantId: string,
): ThreadMessage | null {
  const conv = ensureStore().get(conversationId);
  if (!conv) return null;
  const msg = conv.messages.find((m) => m.id === messageId);
  if (!msg) return null;
  const reactors = [...(msg.reactions[emoji] ?? [])];
  const idx = reactors.indexOf(participantId);
  if (idx >= 0) reactors.splice(idx, 1);
  else reactors.push(participantId);
  const nextReactions = { ...msg.reactions };
  if (reactors.length === 0) delete nextReactions[emoji];
  else nextReactions[emoji] = reactors;
  msg.reactions = nextReactions;
  conv.updated_at = new Date().toISOString();
  return deepClone(msg);
}

export type E2EAppendOutcome =
  | { ok: true; message: ThreadMessage }
  | { ok: false; kind: "conversation_not_found" | "parent_not_found" };

export function e2eTryAppendMessage(
  conversationId: string,
  payload: {
    author: ConversationParticipant;
    body_md: string;
    attachments: Attachment[];
    parent_message_id?: string | null;
  },
): E2EAppendOutcome {
  const conv = ensureStore().get(conversationId);
  if (!conv) return { ok: false, kind: "conversation_not_found" };
  const parentId = payload.parent_message_id ?? null;
  if (parentId && !conv.messages.some((m) => m.id === parentId)) {
    return { ok: false, kind: "parent_not_found" };
  }
  const msg: ThreadMessage = {
    id: crypto.randomUUID(),
    author: payload.author,
    body_md: payload.body_md,
    attachments: payload.attachments,
    created_at: new Date().toISOString(),
    reactions: {},
    parent_message_id: parentId ?? undefined,
  };
  conv.messages.push(msg);
  conv.updated_at = msg.created_at;
  return { ok: true, message: deepClone(msg) };
}

export function e2eCreateConversation(raw: Record<string, unknown>): Conversation {
  const title = typeof raw.title === "string" ? raw.title.trim() : "";
  if (!title) throw new Error("Title is required");

  const bodyMd = typeof raw.body_md === "string" ? raw.body_md : "";
  const tags = Array.isArray(raw.tags)
    ? raw.tags.filter((t): t is string => typeof t === "string")
    : [];

  const urgencyRaw = raw.urgency;
  const urgency: UrgencyLevel =
    urgencyRaw === "info" ||
    urgencyRaw === "normal" ||
    urgencyRaw === "high" ||
    urgencyRaw === "critical"
      ? urgencyRaw
      : "normal";

  const status: StatusLevel =
    urgency === "high" || urgency === "critical" ? "needs-action" : "open";

  let participants: ConversationParticipant[] = [];
  if (Array.isArray(raw.participants)) {
    participants = raw.participants.map((p) => {
      const o = p as Record<string, unknown>;
      const kind = o.kind as ConversationParticipant["kind"];
      return {
        id: String(o.id ?? "unknown"),
        kind: kind ?? "external",
        display_name: typeof o.display_name === "string" ? o.display_name : null,
      };
    });
  }
  if (participants.length === 0) {
    participants = [{ id: "founder", kind: "founder", display_name: "Founder" }];
  }

  const persona =
    typeof raw.persona === "string" && raw.persona.trim() ? raw.persona.trim() : null;

  const attachments: Attachment[] = Array.isArray(raw.attachments)
    ? (raw.attachments as Attachment[])
    : [];

  let space: ConversationSpace = "paperwork-labs";
  const rawSpace = raw.space;
  if (typeof rawSpace === "string" && SPACE_IDS.has(rawSpace as ConversationSpace)) {
    space = rawSpace as ConversationSpace;
  }

  const now = new Date().toISOString();
  const id = `e2e-created-${crypto.randomUUID()}`;
  const author =
    participants.find((p) => p.kind === "founder") ?? participants[0]!;

  const messages: ThreadMessage[] = [];
  if (bodyMd.trim()) {
    messages.push({
      id: `${id}-m1`,
      author,
      body_md: bodyMd.trim(),
      attachments,
      created_at: now,
      reactions: {},
    });
  }

  const conv: Conversation = {
    id,
    title,
    tags,
    urgency,
    persona,
    participants,
    messages,
    created_at: now,
    updated_at: now,
    status,
    snooze_until: null,
    parent_action_id: typeof raw.parent_action_id === "string" ? raw.parent_action_id : null,
    links: null,
    needs_founder_action: status === "needs-action",
    space,
  };
  ensureStore().set(id, conv);
  return deepClone(conv);
}
