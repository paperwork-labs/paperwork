/**
 * Brand color constants — intentionally raw hex.
 *
 * These are the canonical AxiomFolio brand-mark colors. They must not
 * change with dark/light mode (the logo reads the same in both) and so
 * they are NOT routed through the semantic-token system in
 * `index.css`. Centralising them here keeps the "no raw hex in
 * components" rule enforceable while still allowing the brand identity
 * to stay fixed.
 */

/** Star petal — AxiomFolio blue. */
export const BRAND_PETAL = '#3274F0';

/** Center dot — AxiomFolio amber. */
export const BRAND_DOT = '#F59E0B';
