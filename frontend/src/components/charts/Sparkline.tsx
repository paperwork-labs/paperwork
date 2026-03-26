import React from 'react';

type SparklineProps = {
  values?: number[];
  max?: number;
  color?: string;
  height?: number;
};

/** Resolve Chakra-style tokens (e.g. brand.400) and raw CSS for bar fill. */
function resolveBarColor(token: string): string {
  if (token.startsWith('#') || token.startsWith('rgb') || token.startsWith('var(')) {
    return token;
  }
  if (token === 'brand.400' || token === 'brand.500') {
    return 'var(--primary)';
  }
  const dashed = token.replace(/\./g, '-');
  return `var(--chakra-colors-${dashed}, var(--primary))`;
}

const Sparkline: React.FC<SparklineProps> = ({ values = [], max, color = 'brand.400', height = 32 }) => {
  if (!values.length) {
    return <span className="text-xs text-muted-foreground">No samples</span>;
  }
  const safeMax = typeof max === 'number' ? max : Math.max(...values, 1);
  const barColor = resolveBarColor(color);
  return (
    <div className="flex items-end gap-0.5" style={{ height: `${height}px` }}>
      {values.map((value, idx) => {
        const normalized = safeMax ? Math.max((value / safeMax) * 100, 5) : 0;
        return (
          <div
            key={`${value}-${idx}`}
            className="w-1 min-h-[3px] rounded-sm"
            style={{ height: `${normalized}%`, backgroundColor: barColor }}
          />
        );
      })}
    </div>
  );
};

export default Sparkline;
