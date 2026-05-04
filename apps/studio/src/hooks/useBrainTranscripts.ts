"use client";

import { useCallback, useEffect, useState } from "react";

import type { BrainTranscriptListEnvelope, BrainTranscriptListItem } from "@/types/brain-transcripts";

export type BrainTranscriptsLoaded = {
  items: BrainTranscriptListItem[];
  next_cursor: string | null;
};

type BrainTranscriptsState = {
  loading: boolean;
  loadingMore: boolean;
  data: BrainTranscriptsLoaded | undefined;
  error: Error | null;
};

function parseListEnvelope(jsonUnknown: unknown): BrainTranscriptListEnvelope {
  if (typeof jsonUnknown !== "object" || jsonUnknown === null) {
    throw new Error("Unexpected transcripts response shape.");
  }
  const root = jsonUnknown as Record<string, unknown>;
  if (root.success !== true) {
    const err =
      typeof root.error === "string" ? root.error : "Brain transcripts list rejected the request.";
    throw new Error(err);
  }
  if (typeof root.data !== "object" || root.data === null) {
    throw new Error("Transcripts list payload missing.");
  }
  const data = root.data as Record<string, unknown>;
  if (!Array.isArray(data.items)) {
    throw new Error("Transcripts list missing items array.");
  }

  let next_cursor: string | null;
  if (data.next_cursor === null || data.next_cursor === undefined) {
    next_cursor = null;
  } else if (typeof data.next_cursor === "string") {
    next_cursor = data.next_cursor;
  } else {
    throw new Error("Invalid next_cursor in transcripts response.");
  }

  const items: BrainTranscriptListItem[] = [];
  for (const rowUnknown of data.items) {
    if (typeof rowUnknown !== "object" || rowUnknown === null) {
      throw new Error("Invalid transcript row in list.");
    }
    const row = rowUnknown as Record<string, unknown>;
    const id = typeof row.id === "string" ? row.id : "";
    const session_id = typeof row.session_id === "string" ? row.session_id : "";
    const started_at = typeof row.started_at === "string" ? row.started_at : "";
    const ended_at = typeof row.ended_at === "string" ? row.ended_at : "";
    const title = typeof row.title === "string" ? row.title : "";
    if (
      id === ""
      || session_id === ""
      || started_at === ""
      || ended_at === ""
    ) {
      throw new Error("Transcript row missing required string fields.");
    }
    if (typeof row.message_count !== "number" || !Number.isFinite(row.message_count)) {
      throw new Error("Transcript row missing numeric message_count.");
    }
    if (!Array.isArray(row.tags)) {
      throw new Error("Transcript row tags must be an array.");
    }
    const tags: string[] = [];
    for (const t of row.tags) {
      if (typeof t !== "string") {
        throw new Error("Transcript tags must be strings.");
      }
      tags.push(t);
    }
    items.push({
      id,
      session_id,
      started_at,
      ended_at,
      title,
      tags,
      message_count: Math.trunc(row.message_count),
    });
  }

  return { items, next_cursor };
}

async function fetchTranscriptsPage(cursor: string | null): Promise<BrainTranscriptListEnvelope> {
  const params = new URLSearchParams();
  params.set("limit", "50");
  if (cursor) params.set("cursor", cursor);
  const res = await fetch(`/api/admin/brain/transcripts?${params.toString()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });

  let jsonUnknown: unknown;
  try {
    jsonUnknown = await res.json();
  } catch {
    throw new Error(`Brain transcripts proxy returned unreadable JSON (HTTP ${res.status}).`);
  }

  if (!res.ok) {
    const j = jsonUnknown as Record<string, unknown>;
    const msg =
      typeof j.error === "string"
        ? j.error
        : typeof j.detail === "string"
          ? j.detail
          : `Request failed (${res.status}).`;
    throw new Error(msg);
  }

  return parseListEnvelope(jsonUnknown);
}

export function useBrainTranscripts(): BrainTranscriptsState & {
  retry: () => void;
  loadMore: () => void;
} {
  const [state, setState] = useState<BrainTranscriptsState>({
    loading: true,
    loadingMore: false,
    data: undefined,
    error: null,
  });
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setState({
      loading: true,
      loadingMore: false,
      data: undefined,
      error: null,
    });
    try {
      const page = await fetchTranscriptsPage(null);
      setState({
        loading: false,
        loadingMore: false,
        data: { items: page.items, next_cursor: page.next_cursor },
        error: null,
      });
    } catch (e) {
      setState({
        loading: false,
        loadingMore: false,
        data: undefined,
        error: e instanceof Error ? e : new Error("Failed to load transcripts."),
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [tick, load]);

  const retry = useCallback(() => {
    setTick((x) => x + 1);
  }, []);

  const loadMore = useCallback(async () => {
    let cursor: string | null = null;
    setState((prev) => {
      if (prev.loading || prev.loadingMore || !prev.data?.next_cursor) return prev;
      cursor = prev.data.next_cursor;
      return { ...prev, loadingMore: true, error: null };
    });
    if (!cursor) return;

    try {
      const page = await fetchTranscriptsPage(cursor);
      setState((prev) => {
        if (!prev.data) return prev;
        return {
          loading: false,
          loadingMore: false,
          error: null,
          data: {
            items: [...prev.data.items, ...page.items],
            next_cursor: page.next_cursor,
          },
        };
      });
    } catch (e) {
      setState((prev) => ({
        ...prev,
        loadingMore: false,
        error: e instanceof Error ? e : new Error("Failed to load more."),
      }));
    }
  }, []);

  return { ...state, retry, loadMore };
}
