import type { Sprint } from "@/lib/tracker";
import { isSprintActiveForUi } from "@/lib/tracker-reconcile";

const MS_DAY = 86_400_000;

export type Cycle = {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: "active" | "completed" | "upcoming";
};

function parseDateUTC(isoDate: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  const d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo, d));
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function formatISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** ISO-8601 week-year and week number for `d` (UTC calendar date). */
function isoWeekYearAndWeek(d: Date): { isoYear: number; isoWeek: number } {
  const utc = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = utc.getUTCDay();
  const daysFromMonday = (day + 6) % 7;
  const monday = new Date(utc);
  monday.setUTCDate(utc.getUTCDate() - daysFromMonday);
  const thursday = new Date(monday);
  thursday.setUTCDate(monday.getUTCDate() + 3);
  const isoYear = thursday.getUTCFullYear();
  const jan4 = new Date(Date.UTC(isoYear, 0, 4));
  const jan4Dow = jan4.getUTCDay() || 7;
  const weekOneMonday = new Date(jan4);
  weekOneMonday.setUTCDate(jan4.getUTCDate() - (jan4Dow - 1));
  const isoWeek = Math.floor((monday.getTime() - weekOneMonday.getTime()) / (7 * MS_DAY)) + 1;
  return { isoYear, isoWeek };
}

function cycleNameFromStart(start: Date): string {
  const { isoYear, isoWeek } = isoWeekYearAndWeek(start);
  return `Cycle ${isoYear}-W${String(isoWeek).padStart(2, "0")}`;
}

function utcMidnightToday(now: Date): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
}

function defaultAnchorMonday(): Date {
  const t = utcMidnightToday(new Date());
  const day = t.getUTCDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  t.setUTCDate(t.getUTCDate() + mondayOffset);
  return t;
}

/**
 * Pick a 14-day cycle anchor from sprint markdown metadata when possible, else
 * the UTC Monday of the current week.
 */
function resolveCycleAnchor(sprints: Sprint[]): Date {
  const active = sprints.filter((s) => isSprintActiveForUi(s) && s.start);
  const withStart = active
    .map((s) => ({ s, d: s.start ? parseDateUTC(s.start) : null }))
    .filter((x): x is { s: Sprint; d: Date } => x.d != null);
  if (withStart.length === 0) return defaultAnchorMonday();
  withStart.sort((a, b) => a.d.getTime() - b.d.getTime());
  const earliest = withStart[0]!.d;
  const day = earliest.getUTCDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(earliest);
  monday.setUTCDate(earliest.getUTCDate() + mondayOffset);
  return monday;
}

/**
 * Three adjacent 2-week cycles: completed, active (contains `now`), upcoming.
 */
export function buildCyclesFromSprints(sprints: Sprint[], now: Date = new Date()): Cycle[] {
  const anchor = resolveCycleAnchor(sprints);
  const today = utcMidnightToday(now);
  const cycleMs = 14 * MS_DAY;
  const delta = today.getTime() - anchor.getTime();
  const idx = Math.floor(delta / cycleMs);

  const make = (i: number, status: Cycle["status"]): Cycle => {
    const start = new Date(anchor.getTime() + i * cycleMs);
    const end = new Date(anchor.getTime() + (i + 1) * cycleMs - MS_DAY);
    const start_date = formatISODate(start);
    const end_date = formatISODate(end);
    return {
      id: `cycle-${start_date}`,
      name: cycleNameFromStart(start),
      start_date,
      end_date,
      status,
    };
  };

  return [
    make(idx - 1, "completed"),
    make(idx, "active"),
    make(idx + 1, "upcoming"),
  ];
}
