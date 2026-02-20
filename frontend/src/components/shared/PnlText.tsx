import React from 'react';
import { Text } from '@chakra-ui/react';
import { formatMoney } from '../../utils/format';

export interface PnlTextProps {
  value: number;
  format?: 'currency' | 'percent';
  fontSize?: string;
  currency?: string;
  maximumFractionDigits?: number;
}

/** Renders P&L with semantic color (green/red) and optional + sign. */
const PnlText: React.FC<PnlTextProps> = ({
  value,
  format = 'currency',
  fontSize = '12px',
  currency = 'USD',
  maximumFractionDigits = 0,
}) => {
  const isPositive = value > 0;
  const isZero = value === 0;
  const color = isZero ? 'fg.muted' : isPositive ? 'status.success' : 'status.danger';

  let display: string;
  if (format === 'percent') {
    const sign = value > 0 ? '+' : '';
    display = `${sign}${Number(value).toFixed(2)}%`;
  } else {
    const formatted = formatMoney(value, currency, { maximumFractionDigits });
    display = value > 0 ? `+${formatted}` : formatted;
  }

  const arrow = !isZero ? (isPositive ? '\u25B2' : '\u25BC') : '';
  return (
    <Text fontSize={fontSize} color={color} as="span" display="inline-flex" alignItems="center" gap={1}>
      {arrow && <span aria-hidden="true">{arrow}</span>}
      {display}
    </Text>
  );
};

export default PnlText;
