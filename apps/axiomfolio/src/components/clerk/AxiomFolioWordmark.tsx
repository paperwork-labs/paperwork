import AppLogo from "@/components/ui/AppLogo";

/**
 * AxiomFolio brand wordmark for the Clerk auth surfaces. Combines the
 * four-point star mark with the product name typeset to lead the auth card
 * (Q2 2026 wordmark pattern).
 */
export function AxiomFolioWordmark() {
  return (
    <span className="flex items-center gap-3">
      <AppLogo size={56} />
      <span className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
        AxiomFolio
      </span>
    </span>
  );
}
