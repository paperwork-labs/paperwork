import type {
  Conversation,
  ConversationsListPage,
  ConversationSentiment,
  UrgencyLevel,
} from "@/types/conversations";
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

const SUPPORT_FIXTURE_ISO = "2026-02-01T15:30:00.000Z";

const supportCustomerAuthor = {
  id: "e2e-cust-support",
  kind: "external" as const,
  display_name: "Jordan K.",
};

/** Sample support tickets for AxiomFolio product cockpit (WS-76 PR-24a). */
function e2eAxiomfolioSupportConversations(): Conversation[] {
  const mk = (
    id: string,
    title: string,
    status: Conversation["status"],
    sentiment: ConversationSentiment,
    persona: string | null,
    body: string,
  ): Conversation => ({
    id,
    organization_id: null,
    product_slug: "axiomfolio",
    sentiment,
    title,
    tags: ["support", "product-axiomfolio"],
    urgency: status === "needs-action" ? "high" : "normal",
    persona,
    space: "axiomfolio",
    participants: [founderAuthor, supportCustomerAuthor],
    messages: [
      {
        id: `${id}-m1`,
        author: supportCustomerAuthor,
        body_md: body,
        attachments: [],
        created_at: SUPPORT_FIXTURE_ISO,
        reactions: {},
      },
    ],
    created_at: SUPPORT_FIXTURE_ISO,
    updated_at: SUPPORT_FIXTURE_ISO,
    status,
    snooze_until: null,
    parent_action_id: null,
    links: null,
    needs_founder_action: status === "needs-action",
  });

  return [
    mk(
      "e2e-support-axiom-billing",
      "Question about Pro tier billing",
      "open",
      "neutral",
      "coach",
      "Hi — does the Pro plan include real-time risk alerts?",
    ),
    mk(
      "e2e-support-axiom-feature",
      "Feature request: custom benchmark",
      "open",
      "positive",
      "power_user",
      "Love the product. Any chance we can pin a custom benchmark to the overview?",
    ),
    mk(
      "e2e-support-axiom-bug",
      "Bug: CSV export stalls on large portfolios",
      "needs-action",
      "negative",
      "customer",
      "Export spins for 60s+ when universe >500 names — reproducible on our tenant.",
    ),
  ];
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
  const support = e2eAxiomfolioSupportConversations();
  const merged = [...items, ...support];
  return { items: merged, next_cursor: null, total: merged.length };
}

export function getE2EConversationsBadge(): { count: number; hasCritical: boolean } {
  const page = getE2EConversationsListPage();
  const needs = page.items.filter((c) => c.needs_founder_action !== false);
  return {
    count: needs.length,
    hasCritical: needs.some((c) => c.urgency === "critical"),
  };
}
