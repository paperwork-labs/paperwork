export type BrainTranscriptListItem = {
  id: string;
  session_id: string;
  started_at: string;
  ended_at: string;
  title: string;
  tags: string[];
  message_count: number;
};

export type BrainTranscriptListEnvelope = {
  items: BrainTranscriptListItem[];
  next_cursor: string | null;
};

export type BrainTranscriptMessage = {
  turn_index: number;
  user_message: string;
  assistant_message: string;
  summary: string | null;
  ingested_at: string;
};

export type BrainTranscriptDetail = {
  id: string;
  session_id: string;
  started_at: string;
  ended_at: string;
  title: string;
  tags: string[];
  message_count: number;
  messages: BrainTranscriptMessage[];
};
