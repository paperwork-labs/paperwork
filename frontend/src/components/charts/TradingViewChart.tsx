import React, { useEffect, useRef, useState, useCallback } from 'react';
import { X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

import { useColorMode } from '../../theme/colorMode';

interface TradingViewChartProps {
  symbol: string;
  onClose?: () => void;
  height?: number;
  showHeader?: boolean;
  showControls?: boolean;
  interval?: string;
  theme?: 'light' | 'dark';
  style?: string;
  hideSymbolSearch?: boolean;
  autosize?: boolean;
}

const STORAGE_KEY_STUDIES = 'qm.tvStudies';
const STORAGE_KEY_INTERVAL = 'qm.tvInterval';

const AVAILABLE_STUDIES: Record<string, string> = {
  'MAExp@tv-basicstudies': 'EMA',
  'RSI@tv-basicstudies': 'RSI',
  'MACD@tv-basicstudies': 'MACD',
  'Volume@tv-basicstudies': 'Volume',
  'BB@tv-basicstudies': 'Bollinger',
  'VWAP@tv-basicstudies': 'VWAP',
};

const DEFAULT_STUDIES = ['MAExp@tv-basicstudies', 'Volume@tv-basicstudies'];

function getStoredStudies(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_STUDIES);
    return raw ? JSON.parse(raw) : DEFAULT_STUDIES;
  } catch { return DEFAULT_STUDIES; }
}

function getStoredInterval(): string {
  try {
    return localStorage.getItem(STORAGE_KEY_INTERVAL) || 'D';
  } catch { return 'D'; }
}

const getCssColor = (token: string, fallback: string) => {
  if (typeof document === 'undefined') return fallback;
  const varName = token.replace(/\./g, '-');
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${varName}`).trim();
  if (v) {
    if (v.match(/^\d/)) return `rgb(${v})`;
    return v;
  }
  return fallback;
};

const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol,
  onClose,
  height = 500,
  showHeader = true,
  showControls = true,
  interval: intervalProp,
  theme,
  style = '1',
  hideSymbolSearch = false,
  autosize = true,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { colorMode } = useColorMode();

  const [activeStudies, setActiveStudies] = useState<string[]>(getStoredStudies);
  const [interval, setInterval] = useState(intervalProp ?? getStoredInterval());

  const toggleStudy = useCallback((studyId: string) => {
    setActiveStudies(prev => {
      const next = prev.includes(studyId) ? prev.filter(s => s !== studyId) : [...prev, studyId];
      localStorage.setItem(STORAGE_KEY_STUDIES, JSON.stringify(next));
      return next;
    });
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_INTERVAL, interval);
  }, [interval]);

  useEffect(() => {
    if (!chartRef.current) return;

    const container = chartRef.current;
    container.innerHTML = '';

    const effectiveTheme = theme ?? (colorMode === 'dark' ? 'dark' : 'light');
    const toolbarBg = effectiveTheme === 'dark'
      ? getCssColor('bg.panel', '#1E293B')
      : getCssColor('bg.canvas', '#F8FAFC');

    const config = {
      autosize,
      width: autosize ? undefined : '100%',
      height: autosize ? undefined : height - (showHeader ? 60 : 0),
      symbol,
      interval,
      timezone: 'America/New_York',
      theme: effectiveTheme,
      style,
      locale: 'en',
      enable_publishing: false,
      allow_symbol_change: !hideSymbolSearch,
      calendar: true,
      support_host: 'https://www.tradingview.com',
      show_popup_button: true,
      popup_width: '1000',
      popup_height: '650',
      details: true,
      hotlist: true,
      toolbar_bg: toolbarBg,
      withdateranges: true,
      hide_side_toolbar: false,
      studies: activeStudies,
    };

    const wrapper = document.createElement('div');
    wrapper.className = 'tradingview-widget-container';
    wrapper.style.height = '100%';
    wrapper.style.width = '100%';
    const widgetDiv = document.createElement('div');
    widgetDiv.className = 'tradingview-widget-container__widget';
    widgetDiv.style.height = '100%';
    widgetDiv.style.width = '100%';
    wrapper.appendChild(widgetDiv);

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.type = 'text/javascript';
    script.textContent = JSON.stringify(config);
    wrapper.appendChild(script);

    container.appendChild(wrapper);

    return () => {
      container.innerHTML = '';
    };
  }, [symbol, height, showHeader, interval, theme, style, hideSymbolSearch, autosize, colorMode, activeStudies]);

  return (
    <Card
      ref={containerRef}
      style={{ height: `${height}px` }}
      className={cn(
        'relative gap-0 overflow-hidden py-0 shadow-lg ring-1 ring-border',
        'flex flex-col'
      )}
    >
      {showHeader ? (
        <CardHeader className="shrink-0 space-y-0 border-b border-border px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-lg font-bold">{symbol}</div>
              <Badge variant="secondary" className="font-medium">
                Live Chart
              </Badge>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {Object.entries(AVAILABLE_STUDIES).map(([id, label]) => (
                <Button
                  key={id}
                  size="xs"
                  variant={activeStudies.includes(id) ? 'default' : 'outline'}
                  onClick={() => toggleStudy(id)}
                >
                  {label}
                </Button>
              ))}
            </div>

            {showControls ? (
              <div className="flex items-center gap-2">
                {onClose ? (
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Close chart"
                          onClick={onClose}
                        >
                          <X className="size-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Close chart</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                ) : null}
              </div>
            ) : null}
          </div>
        </CardHeader>
      ) : null}

      <CardContent className="flex min-h-0 flex-1 flex-col p-0">
        <div
          ref={chartRef}
          className="h-full min-h-0 w-full bg-[rgb(var(--bg-canvas))]"
        />
      </CardContent>
    </Card>
  );
};

export default TradingViewChart;
