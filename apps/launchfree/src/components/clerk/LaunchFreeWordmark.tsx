/**
 * LaunchFree brand wordmark for the auth pages — slate base + cyan accent
 * matches the marketing landing (`apps/launchfree/src/app/page.tsx`).
 */
export function LaunchFreeWordmark() {
  return (
    <span className="text-3xl font-bold tracking-tight text-slate-50 sm:text-4xl">
      Launch
      <span className="bg-gradient-to-r from-teal-300 to-cyan-400 bg-clip-text text-transparent">
        Free
      </span>
    </span>
  );
}
