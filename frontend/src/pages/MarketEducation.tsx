import React, { useState, useMemo } from 'react';
import {
  Box,
  Heading,
  Text,
  HStack,
  VStack,
  Badge,
  Input,
  Button,
  Code,
  Collapsible,
} from '@chakra-ui/react';
import { FiChevronDown, FiChevronRight, FiSearch } from 'react-icons/fi';

// ---------------------------------------------------------------------------
// Glossary data
// ---------------------------------------------------------------------------

type GlossaryEntry = { term: string; definition: string; formula: string | null };

const GLOSSARY: GlossaryEntry[] = [
  { term: 'SMA (Simple Moving Average)', definition: 'The arithmetic mean of a security\'s price over a specified number of periods. We compute SMAs for 5, 8, 10, 14, 21, 50, 100, 150, and 200 periods.', formula: 'SMA(n) = (P\u2081 + P\u2082 + \u2026 + P\u2099) / n' },
  { term: 'EMA (Exponential Moving Average)', definition: 'A weighted moving average that gives more weight to recent prices. EMAs respond faster to price changes than SMAs. We compute EMAs for 8, 10, 21, and 200 periods.', formula: 'EMA = Price \u00d7 k + EMA(prev) \u00d7 (1 - k), where k = 2/(n+1)' },
  { term: 'RSI (Relative Strength Index)', definition: 'A momentum oscillator measuring the speed and magnitude of price changes on a scale of 0\u2013100. Readings above 70 suggest overbought conditions; below 30 suggests oversold.', formula: 'RSI = 100 - 100/(1 + RS), where RS = Avg Gain / Avg Loss over 14 periods' },
  { term: 'ATR (Average True Range)', definition: 'A volatility indicator showing the average range of price movement. Higher ATR means more volatile. We compute ATR for 14-day and 30-day periods.', formula: 'TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|); ATR = SMA(TR, n)' },
  { term: 'ATRP (ATR Percentage)', definition: 'ATR expressed as a percentage of the current price. Normalizes volatility across different price levels, allowing comparison between a $10 stock and a $1000 stock.', formula: 'ATRP = (ATR / Price) \u00d7 100' },
  { term: 'MACD (Moving Average Convergence Divergence)', definition: 'A trend-following momentum indicator showing the relationship between two EMAs. Signal line crossovers and histogram divergences are key trading signals.', formula: 'MACD Line = EMA(12) - EMA(26); Signal = EMA(9) of MACD; Histogram = MACD - Signal' },
  { term: 'ADX (Average Directional Index)', definition: 'Measures trend strength regardless of direction, on a scale of 0\u2013100. Above 25 indicates a strong trend; below 20 suggests a ranging market. Used with +DI and -DI for direction.', formula: 'DX = |+DI - -DI| / (+DI + -DI) \u00d7 100; ADX = SMA(DX, 14)' },
  { term: 'Bollinger Bands', definition: 'A volatility band placed above and below a moving average. Width expands during volatile periods and contracts during calm periods. Price touching the upper band is not necessarily a sell signal.', formula: 'Upper = SMA(20) + 2\u03c3; Lower = SMA(20) - 2\u03c3; Width = Upper - Lower' },
  { term: 'Stochastic RSI', definition: 'Applies the Stochastic oscillator formula to RSI values, creating a more sensitive momentum indicator. Ranges from 0 to 1.', formula: 'StochRSI = (RSI - RSI_min) / (RSI_max - RSI_min) over 14 periods' },
  { term: 'TD Sequential', definition: 'A Tom DeMark indicator that identifies potential trend exhaustion points. A completed 9-count setup suggests a possible reversal.', formula: 'Buy Setup: 9 consecutive closes below the close 4 bars earlier; Sell Setup: inverse' },
  { term: 'MA Bucket', definition: 'A classification of how well-ordered a stock\'s moving averages are. LEADING means all MAs are stacked bullishly (Price > SMA5 > SMA8 > SMA21 > SMA50 > SMA100 > SMA200). LAGGING is the inverse. NEUTRAL is everything in between.', formula: null },
  { term: 'Market Cap', definition: 'Total market value of a company\'s outstanding shares. Mega Cap: >$200B, Large Cap: $10\u2013200B, Mid Cap: $2\u201310B, Small Cap: $300M\u20132B, Micro Cap: <$300M.', formula: 'Market Cap = Share Price \u00d7 Shares Outstanding' },
  { term: 'P/E Ratio (TTM)', definition: 'Price-to-Earnings ratio using trailing twelve months of earnings. Measures how much investors pay per dollar of earnings. Lower P/E may indicate undervaluation relative to earnings.', formula: 'P/E = Stock Price / Earnings Per Share (TTM)' },
  { term: 'Beta', definition: 'Measures a stock\'s volatility relative to the overall market (S&P 500). Beta > 1 means more volatile than the market; Beta < 1 means less volatile.', formula: '\u03b2 = Cov(R\u209b, R\u2098) / Var(R\u2098)' },
  { term: '52-Week High/Low', definition: 'The highest and lowest price at which a stock has traded during the past 252 trading days. Used to assess current price relative to its annual range.', formula: 'Range Position = (Price - 52W Low) / (52W High - 52W Low) \u00d7 100%' },
  { term: 'Volume (20d Avg)', definition: 'The average daily trading volume over the last 20 trading days. Comparing current volume to this average helps identify unusual activity.', formula: null },
];

// ---------------------------------------------------------------------------
// Indicator deep-dive data
// ---------------------------------------------------------------------------

type DeepDive = {
  title: string;
  sections: { heading: string; body: React.ReactNode }[];
};

const STAGE_DIAGRAM: React.FC = () => (
  <Box position="relative" h="160px" w="100%" my={4} overflow="hidden">
    <svg viewBox="0 0 800 150" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#718096" />
          <stop offset="20%" stopColor="#718096" />
          <stop offset="30%" stopColor="#38A169" />
          <stop offset="55%" stopColor="#38A169" />
          <stop offset="65%" stopColor="#ECC94B" />
          <stop offset="75%" stopColor="#ECC94B" />
          <stop offset="85%" stopColor="#E53E3E" />
          <stop offset="100%" stopColor="#E53E3E" />
        </linearGradient>
      </defs>
      <path
        d="M 0 100 Q 100 100, 150 95 Q 200 90, 250 70 Q 350 20, 450 35 Q 500 42, 550 55 Q 600 70, 650 90 Q 700 110, 800 130"
        fill="none"
        stroke="url(#wave)"
        strokeWidth="3"
      />
      <line x1="0" y1="95" x2="200" y2="88" stroke="#718096" strokeWidth="1.5" strokeDasharray="6 3" opacity="0.6" />
      <line x1="200" y1="88" x2="500" y2="40" stroke="#38A169" strokeWidth="1.5" strokeDasharray="6 3" opacity="0.6" />
      <line x1="500" y1="40" x2="620" y2="60" stroke="#ECC94B" strokeWidth="1.5" strokeDasharray="6 3" opacity="0.6" />
      <line x1="620" y1="60" x2="800" y2="120" stroke="#E53E3E" strokeWidth="1.5" strokeDasharray="6 3" opacity="0.6" />
      <text x="80" y="130" textAnchor="middle" fontSize="13" fontWeight="600" fill="#718096">Stage 1</text>
      <text x="80" y="145" textAnchor="middle" fontSize="10" fill="#A0AEC0">Basing</text>
      <text x="330" y="15" textAnchor="middle" fontSize="13" fontWeight="600" fill="#38A169">Stage 2</text>
      <text x="330" y="30" textAnchor="middle" fontSize="10" fill="#68D391">Advancing</text>
      <text x="560" y="45" textAnchor="middle" fontSize="13" fontWeight="600" fill="#D69E2E">Stage 3</text>
      <text x="560" y="60" textAnchor="middle" fontSize="10" fill="#ECC94B">Distribution</text>
      <text x="730" y="105" textAnchor="middle" fontSize="13" fontWeight="600" fill="#E53E3E">Stage 4</text>
      <text x="730" y="120" textAnchor="middle" fontSize="10" fill="#FC8181">Declining</text>
    </svg>
  </Box>
);

const DEEP_DIVES: DeepDive[] = [
  {
    title: 'Weinstein Stage Analysis',
    sections: [
      {
        heading: 'What it is',
        body: (
          <>
            <Text fontSize="sm" mb={2}>
              Stan Weinstein's four-stage market cycle model, first codified in <em>Secrets for Profiting in Bull and Bear Markets</em> (1988), classifies every stock into one of four lifecycle stages based on the relationship between price and the 30-week simple moving average (SMA).
            </Text>
            <STAGE_DIAGRAM />
          </>
        ),
      },
      {
        heading: 'The four stages',
        body: (
          <VStack align="stretch" gap={3}>
            <Box>
              <HStack mb={1}><Badge variant="subtle" colorPalette="gray">Stage 1</Badge><Text fontSize="sm" fontWeight="semibold">Basing / Accumulation</Text></HStack>
              <Text fontSize="sm">The 30W SMA is flat (slope within &plusmn;0.05%). Price oscillates within ~5% of the SMA. Institutions quietly accumulate. Volume is muted. Duration varies from weeks to years.</Text>
            </Box>
            <Box>
              <HStack mb={1}><Badge variant="subtle" colorPalette="green">Stage 2</Badge><Text fontSize="sm" fontWeight="semibold">Advancing / Markup</Text></HStack>
              <Text fontSize="sm" mb={1}>The 30W SMA is rising (slope &gt;0.05%). Price is above the 30W SMA. This is the only stage to be long.</Text>
              <VStack align="stretch" gap={1} pl={4}>
                <Text fontSize="sm"><strong>2A:</strong> Early advance — price is &le;5% above the 30W SMA.</Text>
                <Text fontSize="sm"><strong>2B:</strong> Healthy trend — price is 5&ndash;15% above the 30W SMA.</Text>
                <Text fontSize="sm"><strong>2C:</strong> Extended — price is &gt;15% above the 30W SMA. Higher risk of pullback.</Text>
              </VStack>
            </Box>
            <Box>
              <HStack mb={1}><Badge variant="subtle" colorPalette="yellow">Stage 3</Badge><Text fontSize="sm" fontWeight="semibold">Distribution / Top</Text></HStack>
              <Text fontSize="sm">Transition phase with choppy, range-bound action. The SMA flattens as large holders distribute to retail. Watch for volume expansion on down days.</Text>
            </Box>
            <Box>
              <HStack mb={1}><Badge variant="subtle" colorPalette="red">Stage 4</Badge><Text fontSize="sm" fontWeight="semibold">Declining / Markdown</Text></HStack>
              <Text fontSize="sm">The 30W SMA is falling (slope &lt;-0.05%). Price is below the 30W SMA. Avoid longs; consider shorts or cash.</Text>
            </Box>
          </VStack>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <VStack align="stretch" gap={2}>
            <Text fontSize="sm">Daily prices are resampled to weekly (Friday close). A 30-week SMA is computed. The slope is expressed as the percentage change vs. the SMA value 5 weeks ago.</Text>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'slope = (SMA_30w_current - SMA_30w_5_weeks_ago) / SMA_30w_5_weeks_ago × 100\n\nStage 1: |slope| ≤ 0.05% AND |price - SMA| / SMA ≤ 5%\nStage 2: slope > 0.05% AND price > SMA\n  2A: distance ≤ 5%   2B: 5% < distance ≤ 15%   2C: distance > 15%\nStage 3: transition (does not meet 1, 2, or 4 criteria)\nStage 4: slope < -0.05% AND price < SMA'}
            </Code>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 537–759; thresholds in config.py</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <Text fontSize="sm">Focus your long exposure on Stage 2 names. Use Stage 1 as a watchlist for potential breakouts. Treat Stage 3 as a warning to tighten stops. Stage 4 should be avoided for longs entirely. The sub-stages (2A/2B/2C) help calibrate position sizing and entry timing — 2A offers the best risk/reward, while 2C suggests you may be late.</Text>
        ),
      },
    ],
  },
  {
    title: 'Mansfield Relative Strength',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">Created by Stan Weinstein, Mansfield Relative Strength measures a stock's performance <em>relative to the S&P 500 (SPY)</em>. It is not the same as RSI — it answers: "Is this stock outperforming or underperforming the broad market over the past year?"</Text>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'Weekly RS Ratio = Stock Close / SPY Close\n52-week SMA of RS Ratio\nMansfield RS = (Current RS / 52W SMA of RS - 1) × 100'}
            </Code>
            <Text fontSize="sm">Values typically range from -30 to +30. A stock at +10 is significantly outperforming the S&P 500 over the trailing year. The benchmark is SPY.</Text>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 638–648</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Positive</strong> = outperforming the S&P 500 on a trailing-year basis.</Text>
            <Text fontSize="sm"><strong>Negative</strong> = underperforming. Even a stock up 20% can have negative Mansfield RS if the S&P did better.</Text>
            <Text fontSize="sm"><strong>Rising RS in Stage 2</strong> = institutional rotation into the name. This is the ideal setup.</Text>
            <Text fontSize="sm"><strong>Falling RS in Stage 2</strong> = warning sign. The stock is advancing but losing momentum vs. the index.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'ATR and Volatility Metrics',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">Average True Range (ATR) is a volatility measure developed by J. Welles Wilder. It captures the average range of price movement including gaps. We compute ATR for 14-day and 30-day lookback periods.</Text>
        ),
      },
      {
        heading: 'Key metrics',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'True Range = max(High - Low, |High - PrevClose|, |Low - PrevClose|)\nATR(14) = 14-day SMA of True Range\nATR(30) = 30-day SMA of True Range\nATRP = (ATR / Current Price) × 100'}
            </Code>
            <Text fontSize="sm"><strong>ATR-distance metrics:</strong> We measure how many ATRs the current price is away from key moving averages (SMA 21, 50, 100, 150). For example, "(P-SMA50)/ATR = 2.5x" means price is 2.5 ATRs above the 50-day SMA — a significantly extended reading.</Text>
            <Text fontSize="sm"><strong>Chandelier Exit:</strong> A trailing stop-loss set at the highest high minus a multiple of ATR (typically 3x). It adapts to volatility — wider stops in volatile names, tighter in calm ones.</Text>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 463–472; atr_engine.py</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>ATRP</strong> normalizes volatility across price levels. A $10 stock with ATR $0.50 and a $500 stock with ATR $25 both have ATRP of 5% — equally volatile in percentage terms.</Text>
            <Text fontSize="sm"><strong>ATR-distance &gt; 3x</strong> from the 21-day SMA is typically extended and prone to mean reversion.</Text>
            <Text fontSize="sm"><strong>ATR-distance &lt; 1x</strong> from a rising SMA is a potential buy-the-dip zone.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'RSI (Relative Strength Index)',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">Developed by J. Welles Wilder in 1978, RSI is a momentum oscillator that measures the speed and magnitude of recent price changes on a 0–100 scale. AxiomFolio uses the standard 14-period lookback with Wilder smoothing.</Text>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'Avg Gain = Wilder-smoothed average of up-day gains over 14 periods\nAvg Loss = Wilder-smoothed average of down-day losses over 14 periods\nRS = Avg Gain / Avg Loss\nRSI = 100 - 100 / (1 + RS)'}
            </Code>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 451–460</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Above 70:</strong> Overbought territory. In a strong uptrend this can persist — it is not an automatic sell signal.</Text>
            <Text fontSize="sm"><strong>Below 30:</strong> Oversold territory. May indicate capitulation or a high-probability bounce in an otherwise healthy stock.</Text>
            <Text fontSize="sm"><strong>Bearish divergence:</strong> Price makes new highs while RSI makes lower highs. Suggests momentum is fading despite rising prices — often precedes a pullback or reversal.</Text>
            <Text fontSize="sm"><strong>Bullish divergence:</strong> Price makes new lows while RSI makes higher lows. Indicates selling pressure is weakening.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'MACD (Moving Average Convergence Divergence)',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">Developed by Gerald Appel, MACD is a trend-following momentum indicator that shows the relationship between two exponential moving averages of price. It consists of three components: the MACD line, the signal line, and the histogram.</Text>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'MACD Line = EMA(12) - EMA(26)\nSignal Line = EMA(9) of MACD Line\nHistogram = MACD Line - Signal Line'}
            </Code>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 56–68</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Signal line crossover (bullish):</strong> MACD crosses above the signal line. Suggests upward momentum is accelerating.</Text>
            <Text fontSize="sm"><strong>Signal line crossover (bearish):</strong> MACD crosses below the signal line. Momentum is slowing or reversing.</Text>
            <Text fontSize="sm"><strong>Zero-line crossover:</strong> MACD crossing above zero means the 12-day EMA has moved above the 26-day EMA — a shift from bearish to bullish intermediate trend.</Text>
            <Text fontSize="sm"><strong>Histogram divergence:</strong> When the histogram shrinks while price trends higher, it warns of waning momentum even before a crossover occurs.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'ADX / Directional Indicators',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">Wilder's Average Directional Index (ADX) measures <em>trend strength</em>, not direction. It is paired with +DI (positive directional indicator) and -DI (negative directional indicator) which show whether buyers or sellers are dominant.</Text>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'+DM = Current High - Previous High (if positive and > -DM, else 0)\n-DM = Previous Low - Current Low (if positive and > +DM, else 0)\n+DI = 100 × Smoothed(+DM) / Smoothed(TR)\n-DI = 100 × Smoothed(-DM) / Smoothed(TR)\nDX = |+DI - -DI| / (+DI + -DI) × 100\nADX = 14-period Wilder-smoothed DX'}
            </Code>
            <Text fontSize="xs" color="fg.muted">Backend: indicator_engine.py lines 70–96</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>ADX &gt; 25:</strong> Strong trend in place. Direction is determined by +DI vs. -DI: if +DI &gt; -DI the trend is up; the opposite means down.</Text>
            <Text fontSize="sm"><strong>ADX &lt; 20:</strong> No meaningful trend. The stock is range-bound, and trend-following strategies will underperform.</Text>
            <Text fontSize="sm"><strong>ADX rising from below 20 to above 25</strong> signals the birth of a new trend — a powerful entry signal when combined with Weinstein Stage 2.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'Volatility Regime (VIX / VVIX / VIX3M)',
    sections: [
      {
        heading: 'What it is',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>VIX:</strong> The CBOE Volatility Index — the market's expectation of 30-day forward volatility, derived from S&P 500 option prices. Often called the "fear gauge."</Text>
            <Text fontSize="sm"><strong>VIX3M:</strong> The 3-month VIX. Captures longer-horizon implied volatility expectations.</Text>
            <Text fontSize="sm"><strong>VVIX:</strong> The volatility of VIX itself — how volatile is the fear gauge? High VVIX means large swings in option premiums.</Text>
          </VStack>
        ),
      },
      {
        heading: 'Key ratios',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'Term Structure Ratio = VIX3M / VIX\n  > 1.0 = Contango (normal market)\n  < 1.0 = Backwardation (fear/stress)\n  > 1.20 = Overbought — protection is expensive\n\nVol-of-Vol Ratio = VVIX / VIX\n  > 6.5 = Protection expensive → sell signal\n  < 3.5 = Protection cheap → buy signal'}
            </Code>
            <Text fontSize="xs" color="fg.muted">Based on CBOE research and Euan Sinclair's <em>Volatility Trading</em>.</Text>
            <Text fontSize="xs" color="fg.muted">Backend: market_data.py volatility-dashboard endpoint</Text>
          </VStack>
        ),
      },
      {
        heading: 'How to interpret it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Contango (ratio &gt; 1.0)</strong> is the normal state — the market expects near-term vol to be lower than 3-month vol. This generally favors equities.</Text>
            <Text fontSize="sm"><strong>Backwardation (ratio &lt; 1.0)</strong> signals acute fear. Near-term risk is perceived as higher than medium-term risk. Historically associated with market selloffs.</Text>
            <Text fontSize="sm"><strong>Vol-of-Vol &gt; 6.5</strong> means the cost of portfolio protection (puts, VIX calls) is elevated. Selling premium is attractive. Conversely, below 3.5 protection is cheap — a good time to buy insurance.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'Bubble / Scatter Chart',
    sections: [
      {
        heading: 'What it is',
        body: (
          <Text fontSize="sm">The multi-dimensional scatter/bubble chart on the Market Dashboard plots stocks across up to four dimensions simultaneously. Each axis can represent any numeric market metric (e.g., RS Mansfield, ATR%, performance), color groups by a categorical dimension, and bubble size encodes a fourth variable.</Text>
        ),
      },
      {
        heading: 'How to read it',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>X-axis / Y-axis:</strong> The two primary numeric metrics being compared. Position along each axis tells you the stock's value for that metric.</Text>
            <Text fontSize="sm"><strong>Color:</strong> Groups stocks by categorical metrics like sector, Weinstein stage, or MA bucket. Same-color clusters reveal correlated behavior within a group.</Text>
            <Text fontSize="sm"><strong>Bubble size:</strong> Typically represents market capitalization or average volume — larger bubbles are bigger, more liquid names.</Text>
          </VStack>
        ),
      },
      {
        heading: 'What to look for',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Clusters:</strong> Stocks grouped together are behaving similarly across both dimensions. This can reveal sector rotation or momentum themes.</Text>
            <Text fontSize="sm"><strong>Outliers:</strong> Stocks far from the cluster may be potential opportunities (if favorably positioned) or risks (if extended).</Text>
            <Text fontSize="sm"><strong>Empty quadrants:</strong> If one quadrant is empty (e.g., high RS + oversold RSI), there are no stocks simultaneously meeting both criteria — which itself is informative about market conditions.</Text>
          </VStack>
        ),
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const GlossaryCard: React.FC<{ entry: GlossaryEntry }> = ({ entry }) => (
  <Box
    borderWidth="1px"
    borderColor="border.subtle"
    borderRadius="lg"
    p={4}
    bg="bg.card"
  >
    <Text fontSize="sm" fontWeight="semibold" mb={1}>{entry.term}</Text>
    <Text fontSize="sm" color="fg.muted" mb={entry.formula ? 2 : 0}>{entry.definition}</Text>
    {entry.formula && (
      <Code fontSize="xs" p={2} borderRadius="md" display="block" whiteSpace="pre-wrap">{entry.formula}</Code>
    )}
  </Box>
);

const DeepDiveSection: React.FC<{ dive: DeepDive }> = ({ dive }) => {
  const [open, setOpen] = useState(false);
  return (
    <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" bg="bg.card" overflow="hidden">
      <Button
        variant="ghost"
        w="100%"
        justifyContent="flex-start"
        px={4}
        py={3}
        borderRadius={0}
        onClick={() => setOpen((v) => !v)}
        _hover={{ bg: 'bg.muted' }}
      >
        <HStack gap={2} w="100%">
          {open ? <FiChevronDown size={16} /> : <FiChevronRight size={16} />}
          <Text fontSize="sm" fontWeight="semibold">{dive.title}</Text>
        </HStack>
      </Button>
      <Collapsible.Root open={open}>
        <Collapsible.Content>
          <VStack align="stretch" gap={4} px={5} pb={5} pt={2}>
            {dive.sections.map((s) => (
              <Box key={s.heading}>
                <Text fontSize="xs" fontWeight="bold" textTransform="uppercase" letterSpacing="wide" color="fg.muted" mb={2}>
                  {s.heading}
                </Text>
                {s.body}
              </Box>
            ))}
          </VStack>
        </Collapsible.Content>
      </Collapsible.Root>
    </Box>
  );
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type TabId = 'glossary' | 'deep-dives';

const MarketEducation: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('glossary');
  const [search, setSearch] = useState('');

  const filteredGlossary = useMemo(() => {
    if (!search.trim()) return GLOSSARY;
    const q = search.toLowerCase();
    return GLOSSARY.filter(
      (g) => g.term.toLowerCase().includes(q) || g.definition.toLowerCase().includes(q),
    );
  }, [search]);

  return (
    <Box p={4}>
      <Box mb={6}>
        <Heading size="md">Market Education</Heading>
        <Text color="fg.muted" fontSize="sm" mt={1}>
          Understanding the indicators, metrics, and methodology behind AxiomFolio's market analysis.
        </Text>
      </Box>

      {/* Tab bar */}
      <HStack gap={1} borderBottomWidth="1px" borderColor="border.subtle" pb={0} mb={4}>
        {(['glossary', 'deep-dives'] as TabId[]).map((tab) => (
          <Button
            key={tab}
            size="sm"
            variant={activeTab === tab ? 'solid' : 'ghost'}
            onClick={() => setActiveTab(tab)}
            borderBottomRadius={0}
          >
            {tab === 'glossary' ? 'Glossary' : 'Indicator Deep-Dives'}
          </Button>
        ))}
      </HStack>

      {/* Glossary tab */}
      {activeTab === 'glossary' && (
        <Box>
          <HStack mb={4} maxW="400px">
            <FiSearch />
            <Input
              placeholder="Search terms..."
              size="sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </HStack>
          {filteredGlossary.length === 0 ? (
            <Text fontSize="sm" color="fg.muted">No terms match "{search}".</Text>
          ) : (
            <Box
              display="grid"
              gridTemplateColumns={{ base: '1fr', md: '1fr 1fr', xl: '1fr 1fr 1fr' }}
              gap={3}
            >
              {filteredGlossary.map((entry) => (
                <GlossaryCard key={entry.term} entry={entry} />
              ))}
            </Box>
          )}
        </Box>
      )}

      {/* Deep-dives tab */}
      {activeTab === 'deep-dives' && (
        <VStack align="stretch" gap={3}>
          {DEEP_DIVES.map((dive) => (
            <DeepDiveSection key={dive.title} dive={dive} />
          ))}
        </VStack>
      )}

      {/* Footer note */}
      <Box mt={8} pt={4} borderTopWidth="1px" borderColor="border.subtle">
        <Text fontSize="xs" color="fg.subtle" fontStyle="italic">
          This page reflects the exact calculations running in our backend. Any time our methodology changes, this page is updated to match.
        </Text>
      </Box>
    </Box>
  );
};

export default MarketEducation;
