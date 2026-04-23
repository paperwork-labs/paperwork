import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

import { formatMoney } from '../../utils/format';
import { cn } from '@/lib/utils';

/** Chakra-style size tokens still passed from table columns — map to CSS length. */
const FONT_SIZE_BY_TOKEN: Record<string, string> = {
  '2xs': '0.625rem',
  xs: '0.75rem',
  sm: '0.875rem',
  md: '1rem',
  lg: '1.125rem',
  xl: '1.25rem',
  '2xl': '1.5rem',
};

/** Chakra-style fontWeight tokens — map to valid CSS font-weight. */
const FONT_WEIGHT_BY_TOKEN: Record<string, React.CSSProperties['fontWeight']> = {
  thin: 100,
  extralight: 200,
  light: 300,
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  extrabold: 800,
  black: 900,
};

export interface PnlTextProps {
  value: number;
  format?: 'currency' | 'percent';
  fontSize?: string;
  fontWeight?: string;
  currency?: string;
  maximumFractionDigits?: number;
}

/** Renders P&L with semantic color (green/red) and optional + sign. */
const PnlText: React.FC<PnlTextProps> = ({
  value,
  format = 'currency',
  fontSize = '12px',
  fontWeight,
  currency = 'USD',
  maximumFractionDigits = 0,
}) => {
  const isPositive = value > 0;
  const isZero = value === 0;
  const colorClass = isZero
    ? 'text-muted-foreground'
    : isPositive
      ? 'text-[rgb(var(--status-success))]'
      : 'text-[rgb(var(--status-danger))]';

  let display: string;
  if (format === 'percent') {
    const sign = value > 0 ? '+' : '';
    display = `${sign}${Number(value).toFixed(2)}%`;
  } else {
    const formatted = formatMoney(value, currency, { maximumFractionDigits });
    display = value > 0 ? `+${formatted}` : formatted;
  }

  const ariaLabel = `${isPositive ? 'Gain' : isZero ? 'No change' : 'Loss'}: ${display}`;
  const resolvedFontSize = FONT_SIZE_BY_TOKEN[fontSize] ?? fontSize;
  const resolvedFontWeight =
    fontWeight === undefined
      ? undefined
      : FONT_WEIGHT_BY_TOKEN[fontWeight] ??
        (Number.isFinite(Number(fontWeight)) ? Number(fontWeight) : fontWeight);
  return (
    <span
      className={cn('inline-flex items-center gap-1 tabular-nums', colorClass)}
      style={{
        fontSize: resolvedFontSize,
        fontWeight: resolvedFontWeight as React.CSSProperties['fontWeight'] | undefined,
      }}
      aria-label={ariaLabel}
    >
      {!isZero &&
        (isPositive ? (
          <ChevronUp className="size-3 shrink-0" aria-hidden />
        ) : (
          <ChevronDown className="size-3 shrink-0" aria-hidden />
        ))}
      {display}
    </span>
  );
};

export default PnlText;
