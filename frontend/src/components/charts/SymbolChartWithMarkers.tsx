import React, { useEffect, useRef } from 'react';
import { Box } from '@chakra-ui/react';
import { useColorMode } from '../../theme/colorMode';

type Bar = { time: string; open: number; high: number; low: number; close: number; volume?: number };
type TradeMarker = { time: string; price: number; type: 'BUY' | 'SELL'; label?: string };
type DividendMarker = { time: string; amount: number; label?: string };

interface Props {
  height?: number;
  bars: Bar[];
  buys: TradeMarker[];
  sells: TradeMarker[];
  dividends: DividendMarker[];
  showTrades?: boolean;
  showDividends?: boolean;
  onHoverDaySec?: (daySec: number | null) => void;
  onClickDaySec?: (daySec: number | null) => void;
  showLine?: boolean;
  avgPrice?: number;
  pinnedDaySec?: number | null;
  zoomYears?: number | 'all';
}

declare global {
  interface Window {
    LightweightCharts?: any;
  }
}

const loadScript = (src: string) =>
  new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject();
    document.body.appendChild(s);
  });

const getCssColor = (token: string, fallback: string) => {
  if (typeof document === 'undefined') return fallback;
  const name = token.replace(/\./g, '-');
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--chakra-colors-${name}`).trim();
  return v || fallback;
};

const SymbolChartWithMarkers: React.FC<Props> = ({
  height = 520,
  bars,
  buys,
  sells,
  dividends,
  showTrades = true,
  showDividends = true,
  onHoverDaySec,
  onClickDaySec,
  showLine = false,
  avgPrice,
  pinnedDaySec,
  zoomYears,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';

  useEffect(() => {
    let chart: any;
    let series: any;

    (async () => {
      if (!window.LightweightCharts) {
        try {
          await loadScript('https://unpkg.com/lightweight-charts@4.2.1/dist/lightweight-charts.standalone.production.js');
        } catch {
          return;
        }
      }
      if (!ref.current) return;

      const bg = isDark ? getCssColor('bg.canvas', '#0F172A') : '#FFFFFF';
      const text = isDark ? getCssColor('fg.default', '#E5E7EB') : '#111827';
      const grid = isDark ? getCssColor('border.subtle', '#1E293B') : '#E5E7EB';

      ref.current.innerHTML = '';
      chart = window.LightweightCharts.createChart(ref.current, {
        height,
        rightPriceScale: { borderVisible: false },
        layout: { background: { color: bg }, textColor: text },
        grid: { vertLines: { color: grid }, horzLines: { color: grid } },
        timeScale: { rightOffset: 5, barSpacing: 6, fixLeftEdge: false, lockVisibleTimeRangeOnResize: false },
        crosshair: { mode: 1 },
      });

      if (showLine) {
        series = chart.addLineSeries({ color: '#38bdf8', lineWidth: 2 });
      } else {
        series = chart.addCandlestickSeries({
          upColor: '#22c55e',
          downColor: '#ef4444',
          borderDownColor: '#ef4444',
          borderUpColor: '#22c55e',
          wickDownColor: '#ef4444',
          wickUpColor: '#22c55e',
        });
      }

      const toDaySec = (iso: string) => {
        const d = new Date(iso);
        return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000);
      };

      if (showLine) {
        series.setData(bars.map((b) => ({ time: toDaySec(b.time), value: b.close })));
      } else {
        series.setData(
          bars.map((b) => ({
            time: toDaySec(b.time),
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          })),
        );
      }

      if (avgPrice && Number.isFinite(avgPrice)) {
        series.createPriceLine({
          price: avgPrice,
          color: '#a78bfa',
          lineWidth: 1,
          lineStyle: window.LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'AVG',
        });
      }

      const raw: Array<{ time: number; text: string; kind: 'B' | 'S' | 'D' }> = [];
      if (showTrades) {
        for (const m of buys) raw.push({ time: toDaySec(m.time), text: m.label || `Buy @ ${m.price.toFixed(2)}`, kind: 'B' });
        for (const m of sells) raw.push({ time: toDaySec(m.time), text: m.label || `Sell @ ${m.price.toFixed(2)}`, kind: 'S' });
      }
      if (showDividends) {
        for (const d of dividends) raw.push({ time: toDaySec(d.time), text: d.label || `Div $${d.amount.toFixed(2)}`, kind: 'D' });
      }

      const grouped = new Map<
        number,
        { texts: string[]; buys: string[]; sells: string[]; divs: string[]; hasB: boolean; hasS: boolean; hasD: boolean }
      >();
      for (const r of raw) {
        const g = grouped.get(r.time) || { texts: [], buys: [], sells: [], divs: [], hasB: false, hasS: false, hasD: false };
        g.texts.push(r.text);
        if (r.kind === 'B') {
          g.buys.push(r.text);
          g.hasB = true;
        }
        if (r.kind === 'S') {
          g.sells.push(r.text);
          g.hasS = true;
        }
        if (r.kind === 'D') {
          g.divs.push(r.text);
          g.hasD = true;
        }
        grouped.set(r.time, g);
      }

      const markers = Array.from(grouped.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([time, g]) => {
          const markerColor = g.hasB && g.hasS ? '#f59e0b' : g.hasB ? '#22c55e' : g.hasS ? '#ef4444' : '#60a5fa';
          const position = g.hasS ? 'aboveBar' : 'belowBar';
          const shape = g.hasD ? 'circle' : g.hasS ? 'arrowDown' : 'arrowUp';
          return {
            time,
            position,
            color: markerColor,
            shape,
            text: g.texts.length > 1 ? `${g.texts.length} events` : g.texts[0],
          };
        });
      series.setMarkers(markers);

      if (typeof zoomYears !== 'undefined' && zoomYears !== 'all' && Number.isFinite(zoomYears)) {
        const end = bars.length ? toDaySec(bars[bars.length - 1].time) : undefined;
        const start = end ? end - Math.floor(Number(zoomYears) * 365.25 * 86400) : undefined;
        if (start && end) chart.timeScale().setVisibleRange({ from: start, to: end });
      } else {
        chart.timeScale().fitContent();
      }

      if (pinnedDaySec) {
        chart.timeScale().setVisibleRange({ from: pinnedDaySec - 86400 * 90, to: pinnedDaySec + 86400 * 90 });
      }

      chart.subscribeCrosshairMove((p: any) => {
        const t = p?.time ?? null;
        onHoverDaySec?.(typeof t === 'number' ? t : null);
      });
      chart.subscribeClick((p: any) => {
        const t = p?.time ?? null;
        onClickDaySec?.(typeof t === 'number' ? t : null);
      });
    })();

    return () => {
      try {
        chart?.remove?.();
      } catch {
        // ignore
      }
    };
  }, [
    height,
    bars,
    buys,
    sells,
    dividends,
    showTrades,
    showDividends,
    onHoverDaySec,
    onClickDaySec,
    showLine,
    avgPrice,
    pinnedDaySec,
    zoomYears,
    isDark,
  ]);

  return <Box ref={ref} w="full" />;
};

export default SymbolChartWithMarkers;


