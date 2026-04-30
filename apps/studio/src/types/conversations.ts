/**
 * TypeScript mirror of the Brain Conversations Pydantic schemas (WS-69 PR E).
 * Keep in sync with apis/brain/app/schemas/conversation.py.
 */

export type ParticipantKind = "founder" | "persona" | "cofounder" | "external";

export interface ConversationParticipant {
  id: string;
  kind: ParticipantKind;
  display_name: string | null;
}

export type AttachmentKind = "image" | "file" | "link";

export interface Attachment {
  id: string;
  kind: AttachmentKind;
  url: string;
  mime: string | null;
  size_bytes: number | null;
  thumbnail_url: string | null;
}

export interface ThreadMessage {
  id: string;
  author: ConversationParticipant;
  body_md: string;
  attachments: Attachment[];
  created_at: string; // ISO 8601
  reactions: Record<string, string[]>; // emoji → participant_ids
}

export type UrgencyLevel = "info" | "normal" | "high" | "critical";
export type StatusLevel = "open" | "needs-action" | "snoozed" | "resolved" | "archived";

export interface ConversationLinks {
  expense_id?: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  tags: string[];
  urgency: UrgencyLevel;
  persona: string | null;
  participants: ConversationParticipant[];
  messages: ThreadMessage[];
  created_at: string;
  updated_at: string;
  status: StatusLevel;
  snooze_until: string | null;
  parent_action_id: string | null;
  links?: ConversationLinks | null;
  /** Brain field — optional on older persisted rows; inbox treats undefined as unknown. */
  needs_founder_action?: boolean;
}

export interface ConversationsListPage {
  items: Conversation[];
  next_cursor: string | null;
  total: number;
}

export interface BrainConversationsResponse {
  success: boolean;
  data: ConversationsListPage | null;
  error?: string;
}

export interface BrainConversationResponse {
  success: boolean;
  data: Conversation | null;
  error?: string;
}

export interface ConversationCreate {
  title: string;
  body_md?: string;
  tags?: string[];
  urgency?: UrgencyLevel;
  persona?: string | null;
  participants?: ConversationParticipant[];
  parent_action_id?: string | null;
  attachments?: Attachment[];
}

export type FilterChip = "needs-action" | "open" | "snoozed" | "resolved" | "all";
