import React, { useEffect, useRef, useMemo } from 'react';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { STAGE_SUBTLE_BADGE } from '@/lib/stageTailwind';
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  HistogramSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesType,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useColorMode } from '../../theme/colorMode';
import type { ChartColors } from '../../hooks/useChartColors';
import {
  detectTrendLines,
  detectSupportResistance,
  detectGaps,
  computeTDSequential,
  computeEMA,
  computeWeinsteinStage,
} from '../../utils/indicators';
import type { OHLCBar, TrendLine, SRLevel, GapZone, TDLabel, EMAResult, StageInfo } from '../../utils/indicators';
import { STAGE_COLORS, RSI_HEX, MACD_HEX, BOLLINGER_HEX } from '../../constants/chart';

type Bar = { time: string; open: number; high: number; low: number; close: number; volume?: number };

export type ChartEventType = 'BUY' | 'SELL' | 'DIVIDEND' | 'TRANSFER' | 'FEE' | 'INTEREST' | 'OTHER'
  | 'ORDER_PENDING' | 'ORDER_FILLED' | 'ORDER_CANCELLED';

export type ChartEvent = {
  time: string;
  price?: number;
  type: ChartEventType;
  label: string;
  amount?: number;
};

export interface IndicatorToggles {
  trendLines: boolean;
  gaps: boolean;
  tdSequential: boolean;
  emas: boolean;
  stage: boolean;
  supportResistance: boolean;
}

const STORAGE_KEY = 'qm.chartIndicators';

export function getStoredIndicators(): IndicatorToggles {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaultIndicators(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultIndicators();
}

export function storeIndicators(t: IndicatorToggles) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
}

function defaultIndicators(): IndicatorToggles {
  return { trendLines: true, gaps: true, tdSequential: true, emas: true, stage: true, supportResistance: true };
}

interface MACDData {
  macd: Array<{ time: string; value: number }>;
  signal: Array<{ time: string; value: number }>;
  histogram: Array<{ time: string; value: number; color?: string }>;
}

interface BollingerData {
  upper: Array<{ time: string; value: number }>;
  lower: Array<{ time: string; value: number }>;
}

interface Props {
  height?: number;
  bars: Bar[];
  events: ChartEvent[];
  showEvents?: boolean;
  onHoverDaySec?: (daySec: number | null) => void;
  onClickDaySec?: (daySec: number | null) => void;
  showLine?: boolean;
  avgPrice?: number;
  pinnedDaySec?: number | null;
  zoomYears?: number | 'all';
  symbol?: string;
  indicators?: IndicatorToggles;
  colors?: ChartColors;
  rsiData?: Array<{ time: string; value: number }>;
  macdData?: MACDData;
  bollingerData?: BollingerData;
  showRSI?: boolean;
  showMACD?: boolean;
  showBollinger?: boolean;
  priceLinesExtra?: Array<{ price: number; color: string; title: string; lineStyle?: number }>;
}

const getCssColor = (token: string, fallback: string) => {
  if (typeof document === 'undefined') return fallback;
  const name = token.replace(/\./g, '-');
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--chakra-colors-${name}`).trim();
  return v || fallback;
};

const toDaySec = (iso: string): UTCTimestamp => {
  const d = new Date(iso);
  return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000) as UTCTimestamp;
};

const asUTC = (t: number) => t as UTCTimestamp;

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return hex;
  return `rgba(${r},${g},${b},${alpha})`;
}

function eventColor(type: ChartEventType, c: ChartColors): string {
  switch (type) {
    case 'BUY': return c.success;
    case 'SELL': return c.danger;
    case 'DIVIDEND': return '#059669';
    case 'TRANSFER': return c.brand500;
    case 'FEE': return c.warning;
    case 'INTEREST': return c.brand700;
    case 'ORDER_PENDING': return c.warning;
    case 'ORDER_FILLED': return c.success;
    case 'ORDER_CANCELLED': return c.muted;
    default: return c.muted;
  }
}

function eventPosition(type: ChartEventType): 'aboveBar' | 'belowBar' {
  const above: Set<ChartEventType> = new Set(['SELL', 'FEE', 'ORDER_PENDING', 'ORDER_FILLED', 'ORDER_CANCELLED']);
  return above.has(type) ? 'aboveBar' : 'belowBar';
}

function eventShape(type: ChartEventType): 'circle' | 'arrowUp' | 'arrowDown' | 'square' {
  if (type === 'ORDER_PENDING') return 'square';
  if (type === 'ORDER_FILLED') return 'arrowDown';
  if (type === 'ORDER_CANCELLED') return 'square';
  return 'circle';
}

function pickEventDayColor(evts: ChartEvent[], c: ChartColors): string {
  const types = new Set(evts.map(e => e.type));
  if (types.has('SELL') || types.has('ORDER_FILLED')) return c.danger;
  if (types.has('ORDER_PENDING')) return c.warning;
  if (types.has('BUY')) return c.success;
  if (types.has('DIVIDEND')) return '#059669';
  return c.muted;
}

const FALLBACK_COLORS: ChartColors = {
  danger: '#F87171', success: '#4ADE80', neutral: '#60A5FA',
  area1: '#34D399', area2: '#60A5FA',
  grid: 'rgba(255,255,255,0.08)', axis: 'rgba(255,255,255,0.45)',
  refLine: 'rgba(255,255,255,0.2)',
  muted: '#94A3B8', subtle: '#64748B', border: '#334155',
  brand500: '#818CF8', brand400: '#A5B4FC', brand700: '#4F46E5',
  warning: '#FBBF24',
  tooltipBg: '#1E293B',
  tooltipBorder: 'rgba(255,255,255,0.12)',
};

const SymbolChartWithMarkers: React.FC<Props> = ({
  height = 520,
  bars,
  events,
  showEvents = true,
  onHoverDaySec,
  onClickDaySec,
  showLine = false,
  avgPrice,
  pinnedDaySec,
  zoomYears,
  symbol,
  indicators,
  colors,
  rsiData,
  macdData,
  bollingerData,
  showRSI = false,
  showMACD = false,
  showBollinger = false,
  priceLinesExtra,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const userHasZoomed = useRef(false);
  const prevSymbol = useRef(symbol);
  const prevZoom = useRef(zoomYears);
  const onHoverRef = useRef(onHoverDaySec);
  const onClickRef = useRef(onClickDaySec);
  onHoverRef.current = onHoverDaySec;
  onClickRef.current = onClickDaySec;
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  const c = colors ?? FALLBACK_COLORS;

  if (symbol !== prevSymbol.current || zoomYears !== prevZoom.current) {
    userHasZoomed.current = false;
    prevSymbol.current = symbol;
    prevZoom.current = zoomYears;
  }

  const ind = indicators ?? defaultIndicators();

  const ohlcBars: OHLCBar[] = useMemo(
    () => bars.map(b => ({ time: toDaySec(b.time), open: b.open, high: b.high, low: b.low, close: b.close })),
    [bars],
  );

  const trendLines: TrendLine[] = useMemo(
    () => (ind.trendLines && ohlcBars.length > 50 ? detectTrendLines(ohlcBars) : []),
    [ohlcBars, ind.trendLines],
  );

  const gapZones: GapZone[] = useMemo(
    () => (ind.gaps ? detectGaps(ohlcBars) : []),
    [ohlcBars, ind.gaps],
  );

  const tdLabels: TDLabel[] = useMemo(
    () => (ind.tdSequential ? computeTDSequential(ohlcBars, isDark ? 'dark' : 'light') : []),
    [ohlcBars, ind.tdSequential, isDark],
  );

  const ema8: EMAResult[] = useMemo(
    () => (ind.emas ? computeEMA(ohlcBars, 8) : []),
    [ohlcBars, ind.emas],
  );
  const ema21: EMAResult[] = useMemo(
    () => (ind.emas ? computeEMA(ohlcBars, 21) : []),
    [ohlcBars, ind.emas],
  );
  const ema200: EMAResult[] = useMemo(
    () => (ind.emas ? computeEMA(ohlcBars, 200) : []),
    [ohlcBars, ind.emas],
  );

  const stageInfo: StageInfo | null = useMemo(
    () => (ind.stage && ohlcBars.length > 60 ? computeWeinsteinStage(ohlcBars) : null),
    [ohlcBars, ind.stage],
  );

  const srLevels: SRLevel[] = useMemo(
    () => (ind.supportResistance && ohlcBars.length > 30 ? detectSupportResistance(ohlcBars) : []),
    [ohlcBars, ind.supportResistance],
  );

  useEffect(() => {
    if (!ref.current) return;

    const bg = isDark ? getCssColor('bg.canvas', '#0F172A') : '#FFFFFF';
    const text = isDark ? getCssColor('fg.default', '#E5E7EB') : '#111827';

    ref.current.innerHTML = '';
    const chart: IChartApi = createChart(ref.current, {
      height,
      rightPriceScale: { borderVisible: false },
      layout: { background: { color: bg }, textColor: text },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      timeScale: { rightOffset: 8, barSpacing: 6, fixLeftEdge: false, lockVisibleTimeRangeOnResize: false },
      crosshair: { mode: 1 },
    });

    let mainSeries: ISeriesApi<SeriesType>;
    if (showLine) {
      mainSeries = chart.addSeries(AreaSeries, {
        lineColor: c.neutral,
        lineWidth: 2,
        topColor: hexToRgba(c.neutral, 0.28),
        bottomColor: hexToRgba(c.neutral, 0.02),
        priceLineVisible: true,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBackgroundColor: c.neutral,
      });
    } else {
      mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: c.success,
        downColor: c.danger,
        borderDownColor: c.danger,
        borderUpColor: c.success,
        wickDownColor: c.danger,
        wickUpColor: c.success,
      });
    }

    const eventMap = new Map<number, ChartEvent[]>();
    if (showEvents) {
      for (const ev of events) {
        const t = toDaySec(ev.time);
        if (t <= 0) continue;
        const arr = eventMap.get(t) || [];
        arr.push(ev);
        eventMap.set(t, arr);
      }
    }

    if (showLine) {
      mainSeries.setData(ohlcBars.map(b => {
        const dayEvts = eventMap.get(b.time);
        const pt: any = { time: asUTC(b.time), value: b.close };
        if (dayEvts && dayEvts.length > 0) {
          const clr = pickEventDayColor(dayEvts, c);
          pt.lineColor = clr;
          pt.topColor = hexToRgba(clr, 0.28);
          pt.bottomColor = hexToRgba(clr, 0.02);
        }
        return pt;
      }));
    } else {
      mainSeries.setData(ohlcBars.map(b => ({ ...b, time: asUTC(b.time) })));
    }

    if (avgPrice && Number.isFinite(avgPrice)) {
      mainSeries.createPriceLine({
        price: avgPrice,
        color: c.brand400,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'AVG',
      });
    }

    if (ind.emas) {
      if (ema8.length > 0) {
        const s = chart.addSeries(LineSeries, { color: c.warning, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ema8.map(e => ({ time: asUTC(e.time), value: e.value })));
      }
      if (ema21.length > 0) {
        const s = chart.addSeries(LineSeries, { color: c.brand500, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ema21.map(e => ({ time: asUTC(e.time), value: e.value })));
      }
      if (ema200.length > 0) {
        const s = chart.addSeries(LineSeries, { color: c.danger, lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false });
        s.setData(ema200.map(e => ({ time: asUTC(e.time), value: e.value })));
      }
    }

    if (ind.trendLines) {
      for (const tl of trendLines) {
        const color = tl.direction === 'up' ? c.success : c.danger;
        const mainLine = chart.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        mainLine.setData([
          { time: asUTC(tl.x1), value: tl.y1 },
          { time: asUTC(tl.x2), value: tl.y2 },
        ]);

        if (tl.channelX1 != null && tl.channelY1 != null && tl.channelX2 != null && tl.channelY2 != null) {
          const channelLine = chart.addSeries(LineSeries, {
            color,
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          channelLine.setData([
            { time: asUTC(tl.channelX1), value: tl.channelY1 },
            { time: asUTC(tl.channelX2), value: tl.channelY2 },
          ]);
        }
      }
    }

    const cIdx = isDark ? 1 : 0;

    // Bollinger bands overlay on main chart pane
    if (showBollinger && bollingerData) {
      if (bollingerData.upper?.length) {
        const upperLine = chart.addSeries(LineSeries, {
          color: BOLLINGER_HEX[cIdx],
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        upperLine.setData(bollingerData.upper.map(d => ({ time: toDaySec(d.time), value: d.value })));
      }
      if (bollingerData.lower?.length) {
        const lowerLine = chart.addSeries(LineSeries, {
          color: BOLLINGER_HEX[cIdx],
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        lowerLine.setData(bollingerData.lower.map(d => ({ time: toDaySec(d.time), value: d.value })));
      }
    }

    if (showEvents && eventMap.size > 0) {
      const ORDER_TYPES: Set<ChartEventType> = new Set(['ORDER_PENDING', 'ORDER_FILLED', 'ORDER_CANCELLED']);
      const markers = Array.from(eventMap.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([time, evts]) => {
          const types = new Set(evts.map(e => e.type));
          const isDividendOnly = types.size === 1 && types.has('DIVIDEND');
          const isOrderOnly = evts.every(e => ORDER_TYPES.has(e.type));
          const hasDividend = types.has('DIVIDEND');
          const divEvt = hasDividend ? evts.find(e => e.type === 'DIVIDEND') : null;
          const divLabel = divEvt && divEvt.amount ? `$${Math.abs(divEvt.amount).toFixed(2)}` : (divEvt?.label || '');

          const orderEvt = isOrderOnly ? evts[0] : null;
          const shape = isDividendOnly ? 'arrowUp'
            : orderEvt ? eventShape(orderEvt.type)
            : 'circle';
          const pos = isDividendOnly ? 'belowBar'
            : (types.has('SELL') || isOrderOnly) ? 'aboveBar'
            : 'belowBar';
          const text = isDividendOnly ? (divLabel ? `DIV ${divLabel}` : 'DIV')
            : orderEvt ? orderEvt.label
            : '';

          return {
            time: asUTC(time),
            position: pos as 'aboveBar' | 'belowBar',
            color: isDividendOnly ? '#059669' : pickEventDayColor(evts, c),
            shape: shape as 'circle' | 'arrowUp' | 'arrowDown' | 'square',
            size: isDividendOnly ? 1.5 : (showLine ? 1 : 0.5),
            text,
          };
        });
      createSeriesMarkers(mainSeries, markers);
    }

    // TD Sequential labels on hidden helper series
    if (ind.tdSequential && tdLabels.length > 0) {
      const tdSeries = chart.addSeries(LineSeries, {
        color: 'transparent',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      tdSeries.setData(ohlcBars.map(b => ({ time: asUTC(b.time), value: b.close })));
      const tdMarkers = tdLabels
        .filter(l => {
          const n = parseInt(l.text.replace('+', ''), 10);
          return l.text.startsWith('+') || n >= 7;
        })
        .map(l => ({
          time: asUTC(l.time),
          position: l.position === 'above' ? 'aboveBar' as const : 'belowBar' as const,
          color: l.color,
          shape: 'circle' as const,
          text: l.text,
        }))
        .sort((a, b) => (a.time as number) - (b.time as number));
      if (tdMarkers.length > 0) createSeriesMarkers(tdSeries, tdMarkers);
    }

    // Gap zones
    if (ind.gaps && gapZones.length > 0) {
      const lastBarTime = ohlcBars.length ? ohlcBars[ohlcBars.length - 1].time : 0;
      for (const gap of gapZones.filter(g => !g.filled)) {
        const isUp = gap.direction === 'up';
        const endTime = gap.filledTime ?? lastBarTime;
        const topData: { time: UTCTimestamp; value: number }[] = [];
          const bottomData: { time: UTCTimestamp; value: number }[] = [];
          for (const bar of ohlcBars) {
            if (bar.time < gap.startTime || bar.time > endTime) continue;
            topData.push({ time: asUTC(bar.time), value: gap.topPrice });
            bottomData.push({ time: asUTC(bar.time), value: gap.bottomPrice });
          }
        if (topData.length === 0) continue;

        const borderColor = isUp ? hexToRgba(c.success, 0.5) : hexToRgba(c.danger, 0.5);
        const fillColor = isUp ? hexToRgba(c.success, 0.12) : hexToRgba(c.danger, 0.12);

        const topSeries = chart.addSeries(LineSeries, {
          color: borderColor, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        topSeries.setData(topData);

        const bottomSeries = chart.addSeries(LineSeries, {
          color: borderColor, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
        });
        bottomSeries.setData(bottomData);

        const fillSeries = chart.addSeries(HistogramSeries, {
          color: fillColor, priceLineVisible: false, lastValueVisible: false, base: gap.bottomPrice,
        });
        fillSeries.setData(topData);
      }
    }

    if (ind.supportResistance && srLevels.length > 0) {
      for (const sr of srLevels) {
        const srColor = sr.type === 'support' ? c.success : c.danger;
        mainSeries.createPriceLine({
          price: sr.price,
          color: hexToRgba(srColor, 0.5),
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: false,
          title: `${sr.type === 'support' ? 'S' : 'R'} (${sr.strength})`,
        });
      }
    }

    if (priceLinesExtra?.length) {
      for (const pl of priceLinesExtra) {
        mainSeries.createPriceLine({
          price: pl.price,
          color: pl.color,
          lineWidth: 1,
          lineStyle: pl.lineStyle ?? LineStyle.Dashed,
          axisLabelVisible: true,
          title: pl.title,
        });
      }
    }

    // RSI sub-pane
    if (showRSI && rsiData?.length) {
      const rsiPane = chart.addPane();
      rsiPane.setStretchFactor(0.15);
      const rsiSeries = rsiPane.addSeries(LineSeries, {
        color: '#7C3AED',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
      });
      rsiSeries.setData(rsiData.map(d => ({ time: toDaySec(d.time), value: d.value })));

      // Overbought (70) and oversold (30) reference lines
      const rsiRefOverBought = rsiPane.addSeries(LineSeries, {
        color: RSI_HEX.overbought[cIdx], lineWidth: 1, lineStyle: LineStyle.Dotted,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      rsiRefOverBought.setData(rsiData.map(d => ({ time: toDaySec(d.time), value: 70 })));

      const rsiRefOverSold = rsiPane.addSeries(LineSeries, {
        color: RSI_HEX.oversold[cIdx], lineWidth: 1, lineStyle: LineStyle.Dotted,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      rsiRefOverSold.setData(rsiData.map(d => ({ time: toDaySec(d.time), value: 30 })));
    }

    // MACD sub-pane
    if (showMACD && macdData) {
      const macdPane = chart.addPane();
      macdPane.setStretchFactor(0.15);

      if (macdData.histogram?.length) {
        const histSeries = macdPane.addSeries(HistogramSeries, {
          priceLineVisible: false,
          lastValueVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
        histSeries.setData(macdData.histogram.map(d => ({
          time: toDaySec(d.time),
          value: d.value,
          color: d.value >= 0 ? MACD_HEX.positive[cIdx] : MACD_HEX.negative[cIdx],
        })));
      }
      if (macdData.macd?.length) {
        const macdLine = macdPane.addSeries(LineSeries, {
          color: '#3B82F6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
        });
        macdLine.setData(macdData.macd.map(d => ({ time: toDaySec(d.time), value: d.value })));
      }
      if (macdData.signal?.length) {
        const signalLine = macdPane.addSeries(LineSeries, {
          color: '#F97316', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
        });
        signalLine.setData(macdData.signal.map(d => ({ time: toDaySec(d.time), value: d.value })));
      }
    }

    // Smart zoom from earliest buy event
    if (!userHasZoomed.current && !pinnedDaySec) {
      const buyTimes = events.filter(e => e.type === 'BUY').map(e => toDaySec(e.time)).filter(t => (t as number) > 0);
      const earliestBuy = buyTimes.length > 0 ? Math.min(...buyTimes.map(t => t as number)) : 0;
      const lastBarTime = ohlcBars.length ? ohlcBars[ohlcBars.length - 1].time : 0;

      if (earliestBuy > 0 && lastBarTime > 0) {
        chart.timeScale().setVisibleRange({
          from: asUTC(earliestBuy - 30 * 86400),
          to: asUTC(lastBarTime + 5 * 86400),
        });
      } else if (typeof zoomYears !== 'undefined' && zoomYears !== 'all' && Number.isFinite(zoomYears)) {
        const end = lastBarTime || undefined;
        const start = end ? end - Math.floor(Number(zoomYears) * 365.25 * 86400) : undefined;
        if (start && end) chart.timeScale().setVisibleRange({ from: asUTC(start), to: asUTC(end) });
      } else {
        chart.timeScale().fitContent();
      }
    }

    if (pinnedDaySec) {
      chart.timeScale().setVisibleRange({
        from: asUTC(pinnedDaySec - 86400 * 90),
        to: asUTC(pinnedDaySec + 86400 * 90),
      });
    }

    let ignoreFirstRangeChange = true;
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
      if (ignoreFirstRangeChange) { ignoreFirstRangeChange = false; return; }
      userHasZoomed.current = true;
    });

    let lastMarkerColor = '';
    let lastMarkerRadius = 0;

    const applyMarkerIfChanged = (color: string, radius: number) => {
      if (color === lastMarkerColor && radius === lastMarkerRadius) return;
      lastMarkerColor = color;
      lastMarkerRadius = radius;
      mainSeries.applyOptions({ crosshairMarkerBackgroundColor: color, crosshairMarkerRadius: radius });
    };

    chart.subscribeCrosshairMove((p: any) => {
      const t = p?.time ?? null;
      onHoverRef.current?.(typeof t === 'number' ? t : null);

      const tooltip = tooltipRef.current;
      if (!tooltip) return;

      if (!p?.point || typeof t !== 'number') {
        if (tooltip) tooltip.style.display = 'none';
        if (showLine) {
          applyMarkerIfChanged(c.neutral, 4);
        }
        return;
      }

      const dayEvts = eventMap.get(t);

      if (showLine) {
        const dotClr = dayEvts?.length ? pickEventDayColor(dayEvts, c) : c.neutral;
        const dotR = dayEvts?.length ? 6 : 4;
        applyMarkerIfChanged(dotClr, dotR);
      }

      if (dayEvts && dayEvts.length > 0) {
        const barData = p.seriesData?.get(mainSeries);
        const price = barData?.value ?? barData?.close ?? 0;
        const rawY = mainSeries.priceToCoordinate(price);
        const y = (rawY != null && rawY > 0) ? rawY : p.point.y;

        if (y != null && ref.current) {
          const chartW = ref.current.clientWidth;
          const tipW = 200;
          const left = p.point.x + 24 + tipW > chartW ? p.point.x - tipW - 12 : p.point.x + 24;
          tooltip.style.left = `${left}px`;
          tooltip.style.top = `${Math.max(10, y - 30)}px`;
          tooltip.style.display = 'block';

          const fmtD = new Date(t * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
          let html = `<div style="font-size:11px;opacity:0.6">${fmtD}</div>`;
          html += `<div style="font-size:13px;font-weight:600;margin:2px 0">$${Number(price).toFixed(2)}</div>`;
          for (const ev of dayEvts) {
            const ec = eventColor(ev.type, c);
            html += `<div style="display:flex;align-items:center;gap:5px;margin-top:3px">`;
            html += `<span style="width:7px;height:7px;border-radius:50%;background:${ec};flex-shrink:0"></span>`;
            html += `<span style="font-size:11px">${ev.label}</span>`;
            html += `</div>`;
          }
          tooltip.innerHTML = html;
        }
      } else {
        tooltip.style.display = 'none';
      }
    });
    chart.subscribeClick((p: any) => {
      const t = p?.time ?? null;
      onClickRef.current?.(typeof t === 'number' ? t : null);
    });

    return () => {
      try { chart?.remove?.(); } catch { /* ignore */ }
    };
  }, [
    height, events, showEvents,
    showLine, avgPrice, pinnedDaySec,
    zoomYears, isDark, ohlcBars, trendLines, gapZones, tdLabels,
    ema8, ema21, ema200, srLevels, ind, c,
    showRSI, rsiData, showMACD, macdData, showBollinger, bollingerData, priceLinesExtra,
  ]);

  const stagePalette = STAGE_COLORS[stageInfo?.stage ?? ''] ?? 'gray';
  const stageBadgeClass = STAGE_SUBTLE_BADGE[stagePalette] ?? STAGE_SUBTLE_BADGE.gray;

  return (
    <div className="relative">
      {stageInfo && ind.stage && (
        <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-2">
          <Badge variant="outline" className={cn('px-2 py-1', stageBadgeClass)}>
            Stage {stageInfo.stage}
          </Badge>
          <Badge variant="outline" className="px-2 py-1">
            SATA {stageInfo.sataScore}/10
          </Badge>
        </div>
      )}
      {ind.emas && (
        <div className="absolute top-2 right-2 z-10 flex flex-wrap gap-1">
          <Badge
            variant="outline"
            className="h-5 border-transparent bg-[rgb(var(--chart-warning)/0.15)] px-2 py-0.5 text-[10px] text-[rgb(var(--chart-warning))]"
          >
            EMA 8
          </Badge>
          <Badge
            variant="outline"
            className="h-5 border-transparent bg-[rgb(var(--chart-neutral)/0.15)] px-2 py-0.5 text-[10px] text-[rgb(var(--chart-neutral))]"
          >
            EMA 21
          </Badge>
          <Badge
            variant="outline"
            className="h-5 border-transparent bg-[rgb(var(--chart-danger)/0.15)] px-2 py-0.5 text-[10px] text-[rgb(var(--chart-danger))]"
          >
            EMA 200
          </Badge>
        </div>
      )}
      <div ref={ref} className="w-full" />
      <div
        ref={tooltipRef}
        style={{
          position: 'absolute',
          display: 'none',
          padding: '8px 12px',
          borderRadius: '8px',
          background: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          border: `1px solid ${c.border}`,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          pointerEvents: 'none' as const,
          zIndex: 20,
          minWidth: '120px',
          maxWidth: '220px',
          backdropFilter: 'blur(8px)',
          color: isDark ? '#E5E7EB' : '#111827',
        }}
      />
    </div>
  );
};

export default SymbolChartWithMarkers;
