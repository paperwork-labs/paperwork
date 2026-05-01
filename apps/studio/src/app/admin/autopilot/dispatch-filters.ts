/** Returns items whose `created_at` falls on the same UTC calendar day as `now`. */
export function filterDispatchesToUtcToday<T extends { created_at: string }>(
  items: T[],
  now: Date = new Date(),
): T[] {
  const y = now.getUTCFullYear();
  const m = now.getUTCMonth();
  const d = now.getUTCDate();
  return items.filter((item) => {
    const dt = new Date(item.created_at);
    return (
      dt.getUTCFullYear() === y && dt.getUTCMonth() === m && dt.getUTCDate() === d
    );
  });
}
