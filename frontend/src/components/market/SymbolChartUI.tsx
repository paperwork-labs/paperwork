/**
 * Shared symbol chart UI: clickable symbol links that open a TradingView chart slide panel.
 * Used by Market Dashboard and Market Tracked pages.
 * Optimized: memoized components, stable callbacks, lazy-loaded chart.
 */
import React, { useCallback, useMemo, memo } from 'react';
import {
  Box,
  HStack,
  Spinner,
  Text,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogBody,
  IconButton,
  PopoverRoot,
  PopoverTrigger,
  PopoverPositioner,
  PopoverContent,
  PopoverBody,
} from '@chakra-ui/react';
import { FiX } from 'react-icons/fi';
import { marketDataApi } from '../../services/api';

export const ChartContext = React.createContext<(symbol: string) => void>(() => {});

const sparklineCache = new Map<string, number[]>();
const sparklineInflight = new Map<string, Promise<number[]>>();

function fetchSparkline(symbol: string): Promise<number[]> {
  if (sparklineCache.has(symbol)) return Promise.resolve(sparklineCache.get(symbol)!);
  const existing = sparklineInflight.get(symbol);
  if (existing) return existing;
  const p = (async () => {
    try {
      const res = await marketDataApi.getHistory(symbol, '1mo', '1d');
      const bars: any[] = (res as any)?.bars || (res as any)?.data || [];
      const closes = bars.map((b: any) => b.close).filter((v: any) => typeof v === 'number');
      sparklineCache.set(symbol, closes);
      return closes;
    } catch {
      sparklineCache.set(symbol, []);
      return [] as number[];
    } finally {
      sparklineInflight.delete(symbol);
    }
  })();
  sparklineInflight.set(symbol, p);
  return p;
}

const SVG_W = 140;
const SVG_H = 32;

const SparklinePopoverContentInner: React.FC<{ symbol: string }> = ({ symbol }) => {
  const [values, setValues] = React.useState<number[] | null>(sparklineCache.get(symbol) ?? null);
  const [loading, setLoading] = React.useState(!sparklineCache.has(symbol));

  React.useEffect(() => {
    if (sparklineCache.has(symbol)) {
      setValues(sparklineCache.get(symbol)!);
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchSparkline(symbol).then((closes) => {
      if (!cancelled) {
        setValues(closes);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const last = values?.length ? values[values.length - 1] : null;
  const prev = values && values.length > 1 ? values[values.length - 2] : null;
  const change = last != null && prev != null && prev !== 0 ? ((last - prev) / prev) * 100 : null;
  const lineColor = change != null ? (change >= 0 ? '#16A34A' : '#DC2626') : '#6366F1';
  const pts = values?.slice(-20) || [];

  const pathD = useMemo(() => {
    if (pts.length < 2) return '';
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const range = max - min || 1;
    return pts
      .map((v, i) => {
        const x = (i / (pts.length - 1)) * SVG_W;
        const y = SVG_H - ((v - min) / range) * (SVG_H - 4) - 2;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }, [pts]);

  return (
    <Box p={2} minW="160px">
      <HStack justify="space-between" mb="2px">
        <Text fontSize="xs" fontWeight="semibold">{symbol}</Text>
        {last != null && change != null && (
          <Text fontSize="10px" fontWeight="medium" color={change >= 0 ? 'green.500' : 'red.500'}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </Text>
        )}
      </HStack>
      {loading ? (
        <HStack gap={1}>
          <Spinner size="xs" />
          <Text fontSize="xs" color="fg.muted">Loading...</Text>
        </HStack>
      ) : pts.length >= 2 ? (
        <>
          <svg width={SVG_W} height={SVG_H} style={{ display: 'block' }}>
            <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {last != null && (
            <Text fontSize="10px" color="fg.muted" mt="2px">${last.toFixed(2)}</Text>
          )}
        </>
      ) : (
        <Text fontSize="xs" color="fg.muted">No data available</Text>
      )}
    </Box>
  );
};

const SparklinePopoverContent = memo(SparklinePopoverContentInner);

const SymbolLinkInner: React.FC<{ symbol: string; children?: React.ReactNode }> = ({ symbol, children }) => {
  const openChart = React.useContext(ChartContext);
  const [hovered, setHovered] = React.useState(false);
  const hoverTimer = React.useRef<ReturnType<typeof setTimeout>>();

  const onEnter = useCallback(() => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(true), 250);
  }, []);
  const onLeave = useCallback(() => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(false), 150);
  }, []);

  React.useEffect(() => () => clearTimeout(hoverTimer.current), []);

  const openAndClose = useCallback(() => {
    setHovered(false);
    openChart(symbol);
  }, [symbol, openChart]);

  const keepOpen = useCallback(() => clearTimeout(hoverTimer.current), []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    openAndClose();
  }, [openAndClose]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      openAndClose();
    }
  }, [openAndClose]);

  return (
    <PopoverRoot open={hovered} positioning={{ placement: 'top' }} lazyMount unmountOnExit>
      <PopoverTrigger asChild>
        <Text
          as="span"
          role="button"
          tabIndex={0}
          fontWeight="medium"
          cursor="pointer"
          _hover={{ textDecoration: 'underline', color: 'brand.500' }}
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
        >
          {children ?? symbol}
        </Text>
      </PopoverTrigger>
      <PopoverPositioner>
        <PopoverContent
          borderRadius="lg"
          shadow="lg"
          borderWidth="1px"
          borderColor="border.subtle"
          bg="bg.panel"
          w="auto"
          onMouseEnter={keepOpen}
          onMouseLeave={onLeave}
        >
          <PopoverBody p={0}>
            <SparklinePopoverContent symbol={symbol} />
          </PopoverBody>
        </PopoverContent>
      </PopoverPositioner>
    </PopoverRoot>
  );
};

export const SymbolLink = memo(SymbolLinkInner);

const TradingViewChartLazy = React.lazy(() => import('../charts/TradingViewChart'));

const ChartSlidePanelInner: React.FC<{ symbol: string | null; onClose: () => void }> = ({ symbol, onClose }) => {
  const chartHeight = typeof window !== 'undefined' ? window.innerHeight - 52 : 400;
  return (
    <DialogRoot open={!!symbol} onOpenChange={(d) => { if (!d.open) onClose(); }}>
      <DialogBackdrop bg="blackAlpha.400" />
      <DialogPositioner
        position="fixed"
        top="0"
        right="0"
        bottom="0"
        display="flex"
        justifyContent="flex-end"
        alignItems="stretch"
        p={0}
        m={0}
      >
        <DialogContent
          position="relative"
          w={{ base: '90vw', lg: '50vw' }}
          maxW="900px"
          h="100vh"
          borderRadius={0}
          borderLeft="1px"
          borderColor="border.subtle"
          bg="bg.panel"
          m={0}
          p={0}
          overflow="hidden"
        >
          <HStack
            justify="space-between"
            align="center"
            px={4}
            py={2}
            borderBottomWidth="1px"
            borderColor="border.subtle"
          >
            <Text fontWeight="semibold" fontSize="sm">{symbol}</Text>
            <IconButton aria-label="Close chart" size="sm" variant="ghost" onClick={onClose}>
              <FiX />
            </IconButton>
          </HStack>
          <DialogBody p={0} flex="1" overflow="hidden">
            {symbol && (
              <React.Suspense fallback={<HStack p={4}><Spinner size="sm" /> <Text fontSize="sm">Loading chart…</Text></HStack>}>
                <TradingViewChartLazy
                  symbol={symbol}
                  onClose={onClose}
                  height={chartHeight}
                  showHeader={false}
                  showControls={false}
                  autosize
                />
              </React.Suspense>
            )}
          </DialogBody>
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
  );
};

export const ChartSlidePanel = memo(ChartSlidePanelInner);
