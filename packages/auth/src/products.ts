/**
 * Canonical product registry for the Paperwork Labs identity surface.
 *
 * `<SignInShell>` reads this list to compose the cross-product attribution
 * line ("Your Paperwork ID also works on …"). Studio and `accounts.*` are
 * intentionally excluded from the customer-facing list because they're
 * internal / identity-host surfaces, not consumer products.
 *
 * Update this file when launching a new customer-facing product so the
 * wordmark explainer stays in sync everywhere.
 */
export interface PaperworkProduct {
  /** Stable lowercase identifier used as the React key + appName lookup. */
  slug: string;
  /** Human display name shown in headlines and the sibling-app explainer. */
  name: string;
  /** Short marketing tagline (used after the wordmark in attribution). */
  tagline: string;
  /** Production marketing/app domain. */
  domain: string;
}

export const PAPERWORK_PRODUCTS: readonly PaperworkProduct[] = [
  {
    slug: "filefree",
    name: "FileFree",
    tagline: "Free tax filing",
    domain: "filefree.ai",
  },
  {
    slug: "launchfree",
    name: "LaunchFree",
    tagline: "Free LLC formation",
    domain: "launchfree.ai",
  },
  {
    slug: "distill",
    name: "Distill",
    tagline: "Compliance automation for platforms.",
    domain: "distill.tax",
  },
  {
    slug: "axiomfolio",
    name: "AxiomFolio",
    tagline: "Portfolio + signals.",
    domain: "axiomfolio.com",
  },
  {
    slug: "trinkets",
    name: "Trinkets",
    tagline: "Free utility tools by FileFree.",
    domain: "tools.filefree.ai",
  },
] as const;

/**
 * Returns the public sibling-product list, optionally excluding the current app.
 * Always excludes Studio (admin) and any internal slugs.
 */
export function getSiblingProducts(currentSlug?: string): readonly PaperworkProduct[] {
  if (!currentSlug) return PAPERWORK_PRODUCTS;
  const normalized = currentSlug.toLowerCase();
  return PAPERWORK_PRODUCTS.filter((p) => p.slug !== normalized);
}

/**
 * Render the "Your Paperwork ID also works on X, Y, Z, and W." string.
 * Uses an Oxford comma + "and" before the last item.
 */
export function formatSiblingExplainer(currentSlug?: string): string {
  const siblings = getSiblingProducts(currentSlug);
  if (siblings.length === 0) {
    return "Your Paperwork ID is the single account for everything Paperwork Labs.";
  }
  const names = siblings.map((p) => p.name);
  let list: string;
  if (names.length === 1) {
    list = names[0]!;
  } else if (names.length === 2) {
    list = `${names[0]} and ${names[1]}`;
  } else {
    const head = names.slice(0, -1).join(", ");
    list = `${head}, and ${names[names.length - 1]}`;
  }
  return `Your Paperwork ID also works on ${list}.`;
}
