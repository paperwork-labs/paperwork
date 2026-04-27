/**
 * Maps legacy semantic token names (Chakra-era) to CSS backgrounds for Storybook design canvas swatches.
 */
export function swatchBackgroundCss(token: string): string {
  const brand: Record<string, string> = {
    'brand.50': '#EFF6FF',
    'brand.100': '#DBEAFE',
    'brand.200': '#BFDBFE',
    'brand.300': '#93C5FD',
    'brand.400': '#60A5FA',
    'brand.500': '#3B82F6',
    'brand.600': '#2563EB',
    'brand.700': '#1D4ED8',
    'brand.800': '#1E40AF',
    'brand.900': '#1E3A8A',
    focusRing: 'rgba(245, 158, 11, 0.25)',
  };
  if (token in brand) return brand[token]!;

  if (token.startsWith('fg.') || token.startsWith('border.')) {
    return `var(--${token.replace(/\./g, '-')})`;
  }
  if (token === 'bg.card') return 'var(--card)';
  if (token.startsWith('status.') || token.startsWith('bg.')) {
    return `rgb(var(--${token.replace(/\./g, '-')}))`;
  }
  return 'var(--muted)';
}
