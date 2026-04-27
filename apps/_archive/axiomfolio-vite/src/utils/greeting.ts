/**
 * Time-aware greeting — warm companion voice.
 *
 * Buckets the hour of day into six moods (early-morning, morning, midday,
 * afternoon, evening, late) and rotates through 2–3 variants per bucket.
 * The rotation is keyed by day-of-year so the greeting shifts each day but
 * stays stable across re-renders within a single day — no jitter as queries
 * tick, no hallucinated novelty.
 *
 * Pure function, no side-effects, fully unit-testable. `now` and `name`
 * are injected so tests do not have to mock `Date.now()`.
 */

export type GreetingBucket =
  | 'early-morning'
  | 'morning'
  | 'midday'
  | 'afternoon'
  | 'evening'
  | 'late';

export interface GreetingInput {
  /** Full name or first name. When absent, greeting falls back to "friend". */
  name?: string | null;
  /** Defaults to `new Date()`. */
  now?: Date;
}

export interface GreetingResult {
  bucket: GreetingBucket;
  text: string;
}

const VARIANTS: Record<GreetingBucket, ReadonlyArray<(n: string) => string>> = {
  'early-morning': [
    (n) => `Early start, ${n}`,
    (n) => `The tape is quiet, ${n} — let's see what opens`,
    (n) => `Morning, ${n}. Coffee first`,
  ],
  morning: [
    (n) => `Good morning, ${n}`,
    (n) => `Morning, ${n} — let's check the book`,
    (n) => `Welcome back, ${n}`,
  ],
  midday: [
    (n) => `Good afternoon, ${n}`,
    (n) => `Midday check-in, ${n}`,
    (n) => `Lunch tape, ${n}`,
  ],
  afternoon: [
    (n) => `Good afternoon, ${n}`,
    (n) => `Afternoon, ${n} — how's the day shaping up?`,
    (n) => `Good to see you back, ${n}`,
  ],
  evening: [
    (n) => `Good evening, ${n}`,
    (n) => `Close is behind us, ${n}`,
    (n) => `Evening, ${n} — time to review`,
  ],
  late: [
    (n) => `Still up, ${n}?`,
    (n) => `Quiet night, ${n} — let's check the tape`,
    (n) => `Late hours, ${n}`,
  ],
};

/**
 * Bucket an hour (0–23) into a greeting mood. Boundaries are inclusive on
 * the lower bound and exclusive on the upper bound so a full day is covered
 * exactly once:
 *   [5, 8)  early-morning
 *   [8, 12) morning
 *   [12,14) midday
 *   [14,17) afternoon
 *   [17,21) evening
 *   [21,5)  late (wraps midnight)
 */
export function bucketForHour(hour: number): GreetingBucket {
  const h = ((Math.floor(hour) % 24) + 24) % 24;
  if (h >= 5 && h < 8) return 'early-morning';
  if (h >= 8 && h < 12) return 'morning';
  if (h >= 12 && h < 14) return 'midday';
  if (h >= 14 && h < 17) return 'afternoon';
  if (h >= 17 && h < 21) return 'evening';
  return 'late';
}

/**
 * Day of the year (1–366) for the given date in local time. Stable key for
 * deterministic greeting rotation.
 */
export function dayOfYear(date: Date): number {
  const start = new Date(date.getFullYear(), 0, 0);
  const diff = date.getTime() - start.getTime();
  return Math.floor(diff / 86_400_000);
}

function firstName(raw: string | null | undefined): string {
  if (raw == null) return 'friend';
  const trimmed = raw.trim();
  if (trimmed.length === 0) return 'friend';
  const [first] = trimmed.split(/\s+/);
  return first && first.length > 0 ? first : 'friend';
}

/**
 * Compute the greeting. Deterministic for a given (bucket, day-of-year) pair
 * — two renders on the same day at the same hour always return the same
 * string, but the next day rotates to the next variant.
 */
export function getTimeAwareGreeting({ name, now = new Date() }: GreetingInput = {}): GreetingResult {
  const bucket = bucketForHour(now.getHours());
  const variants = VARIANTS[bucket];
  const doy = dayOfYear(now);
  const variant = variants[doy % variants.length];
  return {
    bucket,
    text: variant(firstName(name)),
  };
}
