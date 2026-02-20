/**
 * Shared chart and stage color constants for Market and Portfolio sections.
 */

/** Chakra color palette names for stage badges and stage bar segments. */
export const STAGE_COLORS: Record<string, string> = {
  '1': 'blue',
  '2A': 'green',
  '2B': 'green',
  '2C': 'yellow',
  '3': 'orange',
  '4': 'red',
};

/** Harmonized sector/allocation colors (CSS variables for theme awareness). */
const SECTOR_PALETTE = [
  'var(--chakra-colors-brand-600)',
  'var(--chakra-colors-red-500)',
  'var(--chakra-colors-green-500)',
  'var(--chakra-colors-orange-500)',
  'var(--chakra-colors-purple-500)',
  'var(--chakra-colors-teal-500)',
  'var(--chakra-colors-pink-500)',
  'var(--chakra-colors-cyan-600)',
  'var(--chakra-colors-yellow-600)',
  'var(--chakra-colors-brand-400)',
  'var(--chakra-colors-red-400)',
  'var(--chakra-colors-green-600)',
  'var(--chakra-colors-orange-600)',
  'var(--chakra-colors-purple-400)',
] as const;

export { SECTOR_PALETTE };
