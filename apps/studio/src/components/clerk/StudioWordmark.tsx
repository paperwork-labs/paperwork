/**
 * Studio brand wordmark — internal admin surface, parent-brand zinc palette.
 * Used inside the admin variant of `<SignInShell>` (no cross-product explainer).
 */
export function StudioWordmark() {
  return (
    <span className="flex flex-col items-center gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-[0.28em] text-zinc-500">
        Paperwork Labs
      </span>
      <span className="text-3xl font-bold tracking-tight text-zinc-50 sm:text-4xl">
        Studio
      </span>
    </span>
  );
}
