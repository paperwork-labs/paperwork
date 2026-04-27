/**
 * Large brand wordmark used on the FileFree sign-in / sign-up surfaces.
 * Mirrors the typography of `Nav` (`File` + gradient `Free`) but sized up to
 * lead the auth card per the Q2 2026 wordmark pattern.
 */
export function FileFreeWordmark() {
  return (
    <span className="text-3xl font-bold tracking-tight sm:text-4xl">
      File
      <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
        Free
      </span>
    </span>
  );
}
