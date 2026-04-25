import React from 'react';

export interface HistogramBin {
  label: string;
  value: number;
  /** Optional semantic color zone: 'danger' | 'neutral' | 'success' */
  zone?: 'danger' | 'neutral' | 'success';
}

const ZONE_COLORS: Record<string, { bar: string; label: string }> = {
  danger: { bar: 'rgb(var(--status-danger))', label: 'rgb(var(--status-danger))' },
  success: { bar: 'rgb(var(--status-success))', label: 'rgb(var(--status-success))' },
  neutral: { bar: 'rgb(var(--chart-neutral))', label: 'rgb(var(--muted-foreground))' },
};

interface BarHistogramProps {
  bins: HistogramBin[];
  height?: number;
  title?: string;
  subtitle?: string;
  showValues?: boolean;
}

const BarHistogram: React.FC<BarHistogramProps> = ({
  bins,
  height = 160,
  title,
  subtitle,
  showValues = true,
}) => {
  const maxVal = Math.max(...bins.map((b) => b.value), 1);

  return (
    <div>
      {title ? <p className="mb-1 text-sm font-semibold">{title}</p> : null}
      {subtitle ? <p className="mb-2 text-xs text-muted-foreground">{subtitle}</p> : null}
      <div className="flex items-end gap-[3px]" style={{ height: `${height}px` }}>
        {bins.map((b) => {
          const pct = (b.value / maxVal) * 100;
          const zone = b.zone || 'neutral';
          const colors = ZONE_COLORS[zone];
          return (
            <div
              key={b.label}
              className="flex h-full min-w-0 flex-1 flex-col items-center justify-end"
            >
              {showValues && b.value > 0 && (
                <span
                  className="mb-0.5 text-[9px] font-medium"
                  style={{ color: colors.label }}
                >
                  {b.value}
                </span>
              )}
              <div
                className="w-full min-h-[2px] rounded transition-[height] duration-300 ease-out"
                style={{
                  height: `${Math.max(pct, 2)}%`,
                  backgroundColor: colors.bar,
                  opacity: zone === 'neutral' ? 0.75 : 0.85,
                }}
                title={`${b.label}: ${b.value}`}
              />
              <span className="mt-[3px] text-center text-[8px] leading-none text-muted-foreground">
                {b.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default BarHistogram;

export interface TimeSeriesBarProps {
  data: Array<{ date: string; values: Array<{ value: number; color: string; label: string }> }>;
  height?: number;
  title?: string;
  legend?: Array<{ color: string; label: string }>;
}

export const TimeSeriesBar: React.FC<TimeSeriesBarProps> = ({
  data,
  height = 140,
  title,
  legend,
}) => {
  const maxVal = 100;
  const fmtDate = (d: string) => {
    const parts = d.split('-');
    return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : d.slice(5);
  };

  return (
    <div>
      {title ? <p className="mb-1 text-sm font-semibold">{title}</p> : null}
      {legend ? (
        <div className="mb-2 flex flex-wrap gap-3">
          {legend.map((l) => (
            <div key={l.label} className="flex items-center gap-1">
              <span
                className="h-2.5 w-2.5 rounded-sm opacity-70"
                style={{ backgroundColor: l.color }}
              />
              <span className="text-xs text-muted-foreground">{l.label}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="relative flex items-end gap-px" style={{ height: `${height}px` }}>
        {data.map((pt, i) => (
          <div key={i} className="relative h-full min-w-0 flex-1">
            {pt.values.map((v, vi) => {
              const h = (v.value / maxVal) * 100;
              return (
                <div
                  key={vi}
                  className="absolute bottom-0 w-full rounded-sm transition-[height] duration-300 ease-out"
                  style={{
                    backgroundColor: v.color,
                    height: `${h}%`,
                    opacity: 0.5 + vi * 0.15,
                  }}
                  title={`${pt.date}: ${v.value.toFixed(1)}% ${v.label}`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between">
        <span className="text-[9px] text-muted-foreground">{fmtDate(data[0]?.date || '')}</span>
        {data.length > 10 && (
          <span className="text-[9px] text-muted-foreground">
            {fmtDate(data[Math.floor(data.length / 2)]?.date || '')}
          </span>
        )}
        <span className="text-[9px] text-muted-foreground">{fmtDate(data[data.length - 1]?.date || '')}</span>
      </div>
    </div>
  );
};
