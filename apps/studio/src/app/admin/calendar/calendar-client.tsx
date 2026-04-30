"use client";

import { AlertTriangle, Calendar as CalendarLucide, ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { HqEmptyState } from "@/components/admin/hq/HqEmptyState";
import { HqPageHeader } from "@/components/admin/hq/HqPageHeader";
import type { CalendarEventItem } from "@/lib/calendar-events";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export type CalendarClientProps = {
  eventsByDay: Record<string, CalendarEventItem[]>;
};

type CalendarView = "month" | "week" | "agenda";

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function dateKeyLocal(y: number, m0: number, d: number): string {
  return `${y}-${pad2(m0 + 1)}-${pad2(d)}`;
}

function monthMatrix(year: number, month0: number): ({ key: string | null; day: number | null })[] {
  const first = new Date(year, month0, 1);
  const pad = first.getDay();
  const dim = new Date(year, month0 + 1, 0).getDate();
  const cells: ({ key: string | null; day: number | null })[] = [];
  for (let i = 0; i < pad; i++) cells.push({ key: null, day: null });
  for (let d = 1; d <= dim; d++) {
    cells.push({ key: dateKeyLocal(year, month0, d), day: d });
  }
  while (cells.length % 7 !== 0) {
    cells.push({ key: null, day: null });
  }
  return cells;
}

function dotClass(kind: CalendarEventItem["kind"]): string {
  if (kind === "sprint_end") return "bg-[var(--status-warning)]";
  if (kind === "sprint_start") return "bg-[var(--status-info)]";
  return "bg-fuchsia-400";
}

function MonthCalendar({
  year,
  month0,
  todayKey,
  eventsByDay,
  onSelectDay,
  selectedKey,
  onPrevMonth,
  onNextMonth,
  onGoToday,
}: {
  year: number;
  month0: number;
  todayKey: string;
  eventsByDay: Record<string, CalendarEventItem[]>;
  onSelectDay: (key: string | null) => void;
  selectedKey: string | null;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onGoToday: () => void;
}) {
  const cells = useMemo(() => monthMatrix(year, month0), [year, month0]);
  const label = new Date(year, month0, 1).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-zinc-200">{label}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="calendar-nav-prev"
            className="inline-flex h-8 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900/80 px-2 text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-800"
            aria-label="Previous month"
            onClick={onPrevMonth}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            data-testid="calendar-nav-today"
            className="inline-flex h-8 items-center rounded-lg border border-zinc-600 bg-zinc-800/80 px-3 text-xs font-medium text-zinc-200 transition hover:bg-zinc-800"
            onClick={onGoToday}
          >
            Today
          </button>
          <button
            type="button"
            data-testid="calendar-nav-next"
            className="inline-flex h-8 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900/80 px-2 text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-800"
            aria-label="Next month"
            onClick={onNextMonth}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div
        className="overflow-hidden rounded-xl border border-zinc-800/90 bg-zinc-950/50"
        data-testid="calendar-month-grid"
      >
        <div className="grid grid-cols-7 border-b border-zinc-800/80 bg-zinc-900/40">
          {WEEKDAYS.map((w) => (
            <div
              key={w}
              data-testid="calendar-weekday-header"
              className="px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-wider text-zinc-500"
            >
              {w}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 auto-rows-fr">
          {cells.map((cell, i) => {
            if (cell.key == null || cell.day == null) {
              return (
                <div
                  key={`empty-${i}`}
                  className="min-h-[72px] border border-zinc-800/40 bg-zinc-950/30"
                />
              );
            }
            const events = eventsByDay[cell.key] ?? [];
            const isToday = cell.key === todayKey;
            const sprintEnd = events.some((e) => e.kind === "sprint_end");
            const isSelected = selectedKey === cell.key;

            return (
              <button
                key={cell.key}
                type="button"
                data-testid={isToday ? "calendar-day-today" : undefined}
                onClick={() => onSelectDay(cell.key)}
                className={[
                  "flex min-h-[72px] flex-col border border-zinc-800/50 p-1.5 text-left transition",
                  "hover:bg-zinc-900/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--status-info)]",
                  sprintEnd ? "bg-[var(--status-warning)]/[0.07]" : "bg-zinc-950/40",
                  isSelected ? "ring-1 ring-zinc-500/80" : "",
                  isToday ? "ring-2 ring-[var(--status-info)]" : "",
                ].join(" ")}
              >
                <span
                  className={`text-xs font-medium tabular-nums ${isToday ? "text-[var(--status-info)]" : "text-zinc-300"}`}
                >
                  {cell.day}
                </span>
                {events.length > 0 ? (
                  <div className="mt-auto flex flex-wrap gap-0.5 pt-1">
                    {events.slice(0, 4).map((ev) => (
                      <span
                        key={ev.id}
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass(ev.kind)}`}
                        title={ev.title}
                      />
                    ))}
                    {events.length > 4 ? (
                      <span className="text-[9px] text-zinc-500">+{events.length - 4}</span>
                    ) : null}
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function GoogleCalendarCta() {
  return (
    <div
      data-testid="calendar-google-cta"
      className="rounded-xl border p-4"
      style={{
        borderColor: "rgb(217 119 6 / 0.45)",
        backgroundColor: "rgb(120 53 15 / 0.18)",
      }}
    >
      <div className="flex max-w-3xl gap-3">
        <span className="mt-0.5 shrink-0 text-[rgb(253,224,71)]">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium text-[rgb(254,243,199)]">Connect Google Calendar</p>
          <p className="text-sm leading-relaxed text-[rgb(254,229,199)]">
            Connect Google Calendar to see personal events alongside sprints. OAuth wiring is deferred
            to WS-80 — this is a preview of the integration surface.
          </p>
          <button
            type="button"
            disabled
            className="inline-flex cursor-not-allowed rounded-lg border border-[rgb(250,204,21)]/40 bg-zinc-900/40 px-3 py-1.5 text-sm font-medium text-zinc-500"
          >
            Connect (soon)
          </button>
        </div>
      </div>
    </div>
  );
}

export function CalendarClient({ eventsByDay }: CalendarClientProps) {
  const [anchor, setAnchor] = useState(() => new Date());
  const [view, setView] = useState<CalendarView>("month");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const today = useMemo(() => new Date(), []);
  const todayKey = useMemo(
    () => dateKeyLocal(today.getFullYear(), today.getMonth(), today.getDate()),
    [today],
  );

  const y = anchor.getFullYear();
  const m0 = anchor.getMonth();

  const goPrev = useCallback(() => {
    setAnchor(new Date(y, m0 - 1, 1));
  }, [y, m0]);

  const goNext = useCallback(() => {
    setAnchor(new Date(y, m0 + 1, 1));
  }, [y, m0]);

  const goToday = useCallback(() => {
    const t = new Date();
    setAnchor(new Date(t.getFullYear(), t.getMonth(), 1));
    setSelectedKey(null);
  }, []);

  const selectedEvents = selectedKey ? (eventsByDay[selectedKey] ?? []) : [];

  const viewTabs = (
    <div className="inline-flex rounded-lg border border-zinc-800 bg-zinc-900/50 p-0.5">
      {(
        [
          { id: "month" as const, label: "Month" },
          { id: "week" as const, label: "Week" },
          { id: "agenda" as const, label: "Agenda" },
        ] as const
      ).map((t) => (
        <button
          key={t.id}
          type="button"
          data-testid={`calendar-view-${t.id}`}
          onClick={() => setView(t.id)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
            view === t.id
              ? "bg-zinc-800 text-zinc-100 shadow-sm"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <HqPageHeader
        title="Calendar"
        subtitle="Sprint deadlines, milestones, and scheduled tasks"
        actions={viewTabs}
      />

      <GoogleCalendarCta />

      {view === "month" ? (
        <div className="grid gap-6 lg:grid-cols-[1fr,minmax(240px,320px)]">
          <MonthCalendar
            year={y}
            month0={m0}
            todayKey={todayKey}
            eventsByDay={eventsByDay}
            selectedKey={selectedKey}
            onSelectDay={setSelectedKey}
            onPrevMonth={goPrev}
            onNextMonth={goNext}
            onGoToday={goToday}
          />
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Day detail</p>
            <div
              className="rounded-xl border border-zinc-800/90 bg-zinc-950/50 p-4 text-sm"
              data-testid="calendar-day-panel"
            >
              {selectedKey ? (
                <div className="space-y-3">
                  <p className="font-medium text-zinc-200">{selectedKey}</p>
                  <ul className="space-y-2">
                    {selectedEvents.map((ev) => (
                      <li key={ev.id} className="rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3 py-2">
                        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                          {ev.kind.replace(/_/g, " ")}
                        </p>
                        <p className="mt-0.5 text-zinc-200">{ev.title}</p>
                        {ev.meta ? <p className="mt-1 text-xs text-zinc-500">{ev.meta}</p> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-zinc-500">Select a day on the calendar to see deadlines and sprints.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {view === "week" ? (
        <HqEmptyState
          icon={<CalendarLucide className="h-8 w-8" aria-hidden />}
          title="Week view coming soon"
          description="A scrollable week strip with the same event dots will land in a follow-up."
        />
      ) : null}

      {view === "agenda" ? (
        <HqEmptyState
          icon={<CalendarLucide className="h-8 w-8" aria-hidden />}
          title="Agenda view coming soon"
          description="Chronological list of upcoming milestones and tasks will appear here."
        />
      ) : null}
    </div>
  );
}
