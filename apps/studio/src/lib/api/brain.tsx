import { useEffect, useState } from "react";

type ApiEnvelope<T> = { success?: boolean; data?: T; error?: string };

async function readEnvelope<T>(res: Response): Promise<T | null> {
  if (!res.ok) return null;
  try {
    const body = (await res.json()) as ApiEnvelope<T>;
    return body.data ?? null;
  } catch {
    return null;
  }
}

function usePollingJson<T>(path: string, refreshMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setFailed(false);

    const load = async () => {
      try {
        const res = await fetch(path, { cache: "no-store" });
        const payload = await readEnvelope<T>(res);
        if (cancelled) return;
        if (payload === null && !res.ok) {
          setFailed(true);
          return;
        }
        setData(payload);
        setFailed(false);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };

    void load();
    const id = setInterval(() => void load(), refreshMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [path, refreshMs]);

  return { data, error: failed, isLoading: !failed && data === null };
}

export type BrainLearningSummary = {
  as_of: string;
  window_days: number;
  episodes_7d: number;
  lessons_captured_7d: number;
  lesson_rate_pct: number;
  distinct_agents_7d: number;
  top_topics: { topic: string; count: number }[];
  top_agents: { agent: string; count: number }[];
};

export type BrainLearningEpisodeRow = {
  id: number;
  created_at: string | null;
  actor: string;
  event_type: string;
  summary: string;
  tags: string[];
  topic: string;
  persona: string | null;
  product: string | null;
  verified: boolean;
};

export type BrainLearningEpisodesPayload = {
  total: number;
  limit: number;
  offset: number;
  episodes: BrainLearningEpisodeRow[];
};

export type BrainLearningLessonRow = {
  lesson_key: string;
  lesson: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_confirmed_at: string | null;
};

export type BrainLearningLessonsPayload = {
  count: number;
  lessons: BrainLearningLessonRow[];
};

export type BrainLearningTimelinePoint = {
  date: string;
  episodes: number;
  lessons: number;
  agents_involved: number;
};

export type BrainLearningTimelinePayload = {
  days: number;
  series: BrainLearningTimelinePoint[];
};

export function useBrainLearningSummary() {
  return usePollingJson<BrainLearningSummary>("/api/admin/brain/learning/summary", 60_000);
}

export function useBrainLearningTimeline(days = 30) {
  return usePollingJson<BrainLearningTimelinePayload>(
    `/api/admin/brain/learning/timeline?days=${days}`,
    60_000,
  );
}

export function useBrainLearningEpisodes(page: number, topic?: string | null) {
  const offset = page * 25;
  const qs = new URLSearchParams({ limit: "25", offset: String(offset) });
  if (topic) qs.set("topic", topic);
  const path = `/api/admin/brain/learning/episodes?${qs.toString()}`;
  return usePollingJson<BrainLearningEpisodesPayload>(path, 60_000);
}

export function useBrainLearningLessons(search: string) {
  const qs = new URLSearchParams({ limit: "200" });
  if (search.trim()) qs.set("search", search.trim());
  const path = `/api/admin/brain/learning/lessons?${qs.toString()}`;
  return usePollingJson<BrainLearningLessonsPayload>(path, 60_000);
}

export function BrainLearningHeader(props: { lastUpdatedIso: string | null }) {
  const label = formatLocalDateTime(props.lastUpdatedIso);
  return (
    <div className="flex flex-col gap-1 border-b border-zinc-800/80 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Brain learning</h1>
        <p className="mt-1 max-w-2xl text-sm text-zinc-500">
          Continuous learning loop — memory episodes, captured lessons, and agent activity.
        </p>
      </div>
      <p className="text-xs text-zinc-500">
        Last updated{" "}
        <span className="rounded-full border border-zinc-700 bg-zinc-900/60 px-2 py-0.5 font-medium text-zinc-200">
          {label}
        </span>
      </p>
    </div>
  );
}

export function formatLocalDateTime(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}
