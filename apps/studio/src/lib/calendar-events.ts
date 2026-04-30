import type { Sprint } from "@/lib/tracker";
import type { WorkstreamsFile } from "@/lib/workstreams/schema";

export type CalendarEventKind = "sprint_end" | "sprint_start" | "workstream_due";

export type CalendarEventItem = {
  id: string;
  kind: CalendarEventKind;
  title: string;
  meta?: string;
};

/** Normalize JSON date strings to a calendar day key (YYYY-MM-DD). */
export function toDateKey(raw: string): string | null {
  const ymd = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw.trim());
  if (ymd) {
    return `${ymd[1]}-${ymd[2]}-${ymd[3]}`;
  }
  const t = Date.parse(raw);
  if (Number.isNaN(t)) return null;
  const d = new Date(t);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function buildCalendarEventsByDay(
  file: WorkstreamsFile,
  sprints: Sprint[],
): Record<string, CalendarEventItem[]> {
  const acc: Record<string, CalendarEventItem[]> = {};

  const push = (key: string | null, ev: CalendarEventItem) => {
    if (!key) return;
    if (!acc[key]) acc[key] = [];
    acc[key].push(ev);
  };

  for (const ws of file.workstreams) {
    if (!ws.due_at) continue;
    const key = toDateKey(ws.due_at);
    push(key, {
      id: `ws-${ws.id}`,
      kind: "workstream_due",
      title: ws.title,
      meta: ws.id,
    });
  }

  for (const sp of sprints) {
    if (sp.end) {
      const key = toDateKey(sp.end);
      push(key, {
        id: `sprint-end-${sp.slug}`,
        kind: "sprint_end",
        title: sp.title,
        meta: `Sprint ends · ${sp.slug}`,
      });
    }
    if (sp.start) {
      const key = toDateKey(sp.start);
      push(key, {
        id: `sprint-start-${sp.slug}`,
        kind: "sprint_start",
        title: sp.title,
        meta: `Sprint starts · ${sp.slug}`,
      });
    }
  }

  for (const k of Object.keys(acc)) {
    acc[k]!.sort((a, b) =>
      `${a.kind} ${a.title}`.localeCompare(`${b.kind} ${b.title}`, "en"),
    );
  }

  return acc;
}
