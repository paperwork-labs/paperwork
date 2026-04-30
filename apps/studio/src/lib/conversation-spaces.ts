import rawSpaces from "@/data/conversation-spaces.json";
import type { Conversation, ConversationSpace } from "@/types/conversations";

export type SpaceGlyphId = "user" | "building" | "chart" | "file" | "book" | "alert";

export interface ConversationSpaceMeta {
  id: ConversationSpace;
  name: string;
  icon: SpaceGlyphId;
  description: string;
}

export const CONVERSATION_SPACES = rawSpaces as ConversationSpaceMeta[];

const TOPIC_SPACE_RULES: { re: RegExp; space: ConversationSpace }[] = [
  { re: /\baxiomfolio\b|portfolio\s+(risk|metrics)|\bfolio\b/i, space: "axiomfolio" },
  { re: /\bfilefree\b/i, space: "filefree" },
  { re: /\brunbook\b|\bprocedure\b|\bsop\b|playbook/i, space: "runbook-asks" },
  { re: /\bincident\b|post[\s-]?mortem|\boutage\b|\bsev[- ]?[0-9]/i, space: "incidents" },
  { re: /\bpersonal\b|\bprivate\b(?!\s+repo)/i, space: "personal" },
];

export function inferSpaceFromTopic(title: string): ConversationSpace {
  const t = title.trim();
  if (!t) return "paperwork-labs";
  for (const rule of TOPIC_SPACE_RULES) {
    if (rule.re.test(t)) return rule.space;
  }
  return "paperwork-labs";
}

export function effectiveConversationSpace(c: Pick<Conversation, "space">): ConversationSpace {
  return c.space ?? "paperwork-labs";
}

export function spaceDisplayName(space: ConversationSpace): string {
  return CONVERSATION_SPACES.find((s) => s.id === space)?.name ?? space;
}
