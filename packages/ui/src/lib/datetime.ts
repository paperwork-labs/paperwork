/**
 * Display helpers for API timestamps (UTC) in the user's local or chosen timezone.
 *
 * @example
 * ```ts
 * // Server sent: "2026-04-27T15:30:00.000Z"
 * formatInUserTZ("2026-04-27T15:30:00.000Z");
 * // e.g. "4/27/2026, 11:30:00 AM" in America/New_York (host default)
 * ```
 *
 * @example
 * ```ts
 * formatInUserTZ("2026-04-27T15:30:00.000Z", "Europe/London", {
 *   dateStyle: "medium",
 *   timeStyle: "short",
 * });
 * ```
 */
export function formatInUserTZ(
  iso: string,
  timeZone?: string,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  const tz =
    timeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
  return new Intl.DateTimeFormat(undefined, {
    timeZone: tz,
    ...options,
  }).format(d);
}
