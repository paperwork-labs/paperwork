import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box,
  Button,
  CardBody,
  CardHeader,
  CardRoot,
  Text,
  HStack,
  Badge,
  IconButton,
  TooltipRoot,
  TooltipTrigger,
  TooltipPositioner,
  TooltipContent,
} from '@chakra-ui/react';
import { FiExternalLink, FiX } from 'react-icons/fi';
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
  const name = token.replace(/\./g, '-');
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--chakra-colors-${name}`).trim();
  return v || fallback;
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
  const themeRef = useRef(theme ?? (colorMode === 'dark' ? 'dark' : 'light'));

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
    themeRef.current = effectiveTheme;
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

  const openInTradingView = useCallback(() => {
    const url = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;
    window.open(url, '_blank', 'width=1200,height=800');
  }, [symbol]);

  return (
    <CardRoot
      bg="bg.card"
      borderColor="border.subtle"
      borderWidth="1px"
      ref={containerRef}
      h={`${height}px`}
      position="relative"
      overflow="hidden"
      shadow="lg"
    >
      {showHeader ? (
        <CardHeader py={3} px={4} borderBottomWidth="1px" borderColor="border.subtle">
          <HStack justify="space-between" align="center" flexWrap="wrap" gap={2}>
            <HStack gap={3}>
              <Text fontWeight="bold" fontSize="lg">
                {symbol}
              </Text>
              <Badge colorPalette="blue" variant="subtle">
                Live Chart
              </Badge>
            </HStack>

            <HStack gap={2} flexWrap="wrap">
              {Object.entries(AVAILABLE_STUDIES).map(([id, label]) => (
                <Button
                  key={id}
                  size="xs"
                  variant={activeStudies.includes(id) ? 'solid' : 'outline'}
                  onClick={() => toggleStudy(id)}
                >
                  {label}
                </Button>
              ))}
            </HStack>

            {showControls ? (
              <HStack gap={2}>
                <TooltipRoot>
                  <TooltipTrigger asChild>
                    <IconButton aria-label="Open full TradingView with your saved indicators and Pine Scripts" size="sm" variant="ghost" onClick={openInTradingView}>
                      <FiExternalLink />
                    </IconButton>
                  </TooltipTrigger>
                  <TooltipPositioner>
                    <TooltipContent>Open full TradingView with your saved indicators and Pine Scripts</TooltipContent>
                  </TooltipPositioner>
                </TooltipRoot>

                {onClose ? (
                  <TooltipRoot>
                    <TooltipTrigger asChild>
                      <IconButton aria-label="Close chart" size="sm" variant="ghost" onClick={onClose}>
                        <FiX />
                      </IconButton>
                    </TooltipTrigger>
                    <TooltipPositioner>
                      <TooltipContent>Close chart</TooltipContent>
                    </TooltipPositioner>
                  </TooltipRoot>
                ) : null}
              </HStack>
            ) : null}
          </HStack>
        </CardHeader>
      ) : null}

      <CardBody p={0} h="full">
        <Box ref={chartRef} h="full" w="full" bg="bg.canvas" />
      </CardBody>
    </CardRoot>
  );
};

export default TradingViewChart;


