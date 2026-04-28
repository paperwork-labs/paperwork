/**
 * Typography-only wordmark for the primary Clerk host (no product image assets).
 */
export function PaperworkLabsWordmark() {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-lg font-semibold tracking-tight text-slate-100 sm:text-xl">
        Paperwork Labs
      </span>
      <span className="text-xs font-medium text-slate-400">Identity</span>
    </div>
  );
}
