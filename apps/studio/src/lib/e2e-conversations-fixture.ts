import type { Conversation, ConversationsListPage, UrgencyLevel } from "@/types/conversations";
import founderActions from "@/data/founder-actions.json";
import type { FounderActionsPayload } from "@/lib/founder-actions-source";

function slugify(text: string): string {
  const s = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120);
  return s || "action";
}

const FIXTURE_ISO = "2026-01-15T12:00:00.000Z";

const founderAuthor = {
  id: "founder",
  kind: "founder" as const,
  display_name: "Founder",
};

type FounderActionItem = NonNullable<NonNullable<FounderActionsPayload["tiers"]>[number]["items"]>[number];

function bodyFromItem(item: FounderActionItem): string {
  const parts: string[] = [];
  if (item.why) parts.push(`**Why:** ${item.why}`);
  if (item.where) parts.push(`**Where:** ${item.where}`);
  if (item.steps?.length) parts.push(`**Steps:**\n${item.steps.join("\n")}`);
  if (item.verification) parts.push(`**Verification:** ${item.verification}`);
  if (item.eta) parts.push(`**ETA:** ${item.eta}`);
  return parts.join("\n\n");
}

function itemUrgency(tierId: string, item: { urgency?: string }): UrgencyLevel {
  const u = item.urgency;
  if (u === "info" || u === "normal" || u === "high" || u === "critical") return u;
  return tierId === "critical" ? "critical" : "normal";
}

/**
 * Deterministic Conversations list for Playwright when STUDIO_E2E_FIXTURE=1
 * (mirrors Brain backfill shape: needs-action + needs_founder_action).
 */
export function getE2EConversationsListPage(): ConversationsListPage {
  const payload = founderActions as FounderActionsPayload;
  const items: Conversation[] = [];
  for (const tier of payload.tiers ?? []) {
    const tierId = String(tier.id ?? "operational");
    for (const it of tier.items ?? []) {
      const title = String(it.title ?? "").trim();
      if (!title) continue;
      const id = `e2e-fa-${slugify(title)}`;
      const parent = slugify(title);
      const body = bodyFromItem(it);
      const tags = [tierId, "founder-action"];
      if (typeof it.source === "string" && it.source.trim()) {
        const slug = slugify(it.source).slice(0, 40);
        if (slug) tags.push(`founder-src-${slug}`);
      }
      const urgency = itemUrgency(tierId, it);
      items.push({
        id,
        title,
        tags,
        urgency,
        persona: null,
        participants: [founderAuthor],
        messages: body
          ? [
              {
                id: `${id}-m1`,
                author: founderAuthor,
                body_md: body,
                attachments: [],
                created_at: FIXTURE_ISO,
                reactions: {},
              },
            ]
          : [],
        created_at: FIXTURE_ISO,
        updated_at: FIXTURE_ISO,
        status: "needs-action",
        snooze_until: null,
        parent_action_id: parent,
        links: null,
        needs_founder_action: true,
      });
    }
  }
  return { items, next_cursor: null, total: items.length };
}

export function getE2EConversationsBadge(): { count: number; hasCritical: boolean } {
  const page = getE2EConversationsListPage();
  const needs = page.items.filter((c) => c.needs_founder_action !== false);
  return {
    count: needs.length,
    hasCritical: needs.some((c) => c.urgency === "critical"),
  };
}
