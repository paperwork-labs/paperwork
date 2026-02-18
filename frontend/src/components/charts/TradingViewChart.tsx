import React, { useEffect, useRef } from 'react';
import {
  Box,
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
  interval = 'D',
  theme,
  style = '1',
  hideSymbolSearch = false,
  autosize = true,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { colorMode } = useColorMode();

  useEffect(() => {
    if (!chartRef.current) return;

    const container = chartRef.current;
    container.innerHTML = '';

    const effectiveTheme = theme ?? (colorMode === 'dark' ? 'dark' : 'light');
    const toolbarBg = effectiveTheme === 'dark'
      ? getCssColor('bg.panel', '#1E293B')
      : getCssColor('bg.canvas', '#F8FAFC');

    const config = {
      autosize: autosize,
      width: autosize ? undefined : '100%',
      height: autosize ? undefined : height - (showHeader ? 60 : 0),
      symbol: symbol,
      interval: interval,
      timezone: 'America/New_York',
      theme: effectiveTheme,
      style: style,
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
  }, [symbol, height, showHeader, interval, theme, style, hideSymbolSearch, autosize, colorMode]);

  const openInTradingView = () => {
    const url = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;
    window.open(url, '_blank', 'width=1200,height=800');
  };

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
          <HStack justify="space-between" align="center">
            <HStack gap={3}>
              <Text fontWeight="bold" fontSize="lg">
                {symbol}
              </Text>
              <Badge colorPalette="blue" variant="subtle">
                Live Chart
              </Badge>
            </HStack>

            {showControls ? (
              <HStack gap={2}>
                <TooltipRoot>
                  <TooltipTrigger asChild>
                    <IconButton aria-label="Open in TradingView" size="sm" variant="ghost" onClick={openInTradingView}>
                      <FiExternalLink />
                    </IconButton>
                  </TooltipTrigger>
                  <TooltipPositioner>
                    <TooltipContent>Open in TradingView</TooltipContent>
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


