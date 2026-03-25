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
  SimpleGrid,
} from '@chakra-ui/react';
import { FiChevronDown, FiChevronRight, FiSearch } from 'react-icons/fi';
import { STAGE_HEX } from '../constants/chart';
import { useColorMode } from '../theme/colorMode';

type GlossaryEntry = { term: string; definition: string; formula: string | null };

type StageKey = '1A' | '1B' | '2A' | '2B' | '2C' | '3A' | '3B' | '4A' | '4B' | '4C';

/** Tinted card aligned to STAGE_HEX (chart / legend); readable in light and dark. */
const SubStageCard: React.FC<{
  stage: StageKey;
  badgePalette: 'red' | 'gray' | 'green' | 'yellow' | 'orange';
  children: React.ReactNode;
}> = ({ stage, badgePalette, children }) => {
  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';
  const hex = STAGE_HEX[stage][isDark ? 1 : 0];
  const base = isDark ? '#1e293b' : '#ffffff';
  const bgMixed = `color-mix(in srgb, ${hex} ${isDark ? 24 : 18}%, ${base})`;

  return (
    <Box
      p={3}
      borderRadius="md"
      borderWidth="1px"
      borderColor="border.subtle"
      borderLeftWidth="3px"
      borderLeftColor={hex}
      style={{ backgroundColor: bgMixed }}
    >
      <Badge colorPalette={badgePalette} variant="subtle" mb={1}>
        {stage}
      </Badge>
      <Text fontSize="xs" color="fg.muted">
        {children}
      </Text>
    </Box>
  );
};

const GLOSSARY: GlossaryEntry[] = [
  { term: 'SMA (Simple Moving Average)', definition: 'Arithmetic mean of price over N periods. Key SMAs: 21, 50, 100, 150 (primary stage anchor), 200.', formula: 'SMA(n) = (P₁ + P₂ + … + Pₙ) / n' },
  { term: 'EMA (Exponential Moving Average)', definition: 'Weighted average giving more weight to recent prices. Key EMAs: 10 (short-term trend), 21, 200.', formula: 'EMA = Price × k + EMA(prev) × (1 - k), where k = 2/(n+1)' },
  { term: 'RSI (Relative Strength Index)', definition: 'Momentum oscillator (0–100) using Wilder smoothing. Above 70 = overbought, below 30 = oversold.', formula: 'RS = Wilder Avg Gain / Wilder Avg Loss; RSI = 100 - 100/(1+RS)' },
  { term: 'ATR (Average True Range)', definition: 'Volatility measure — average range of price movement. ATR%14 normalizes across price levels.', formula: 'TR = max(H-L, |H-PrevC|, |L-PrevC|); ATR = SMA(TR, 14)' },
  { term: 'ATRP (ATR Percentage)', definition: 'ATR as a % of current price. A $10 stock with ATR $0.50 and a $500 stock with ATR $25 both have ATRP 5%.', formula: 'ATRP = (ATR / Price) × 100' },
  { term: 'Extension % (Ext%)', definition: 'How far price has moved from SMA150 — the primary distance metric in Stage Analysis.', formula: 'Ext% = (Close - SMA150) / SMA150 × 100' },
  { term: 'ATRE (ATR Extensions)', definition: 'Price distance from key MAs measured in ATRs. ATRE_150 > 6.0 triggers the 2C override.', formula: 'ATRE_150 = (Close - SMA150) / ATR14' },
  { term: 'EMA10 Distance (Normalized)', definition: 'How far price is from EMA10, normalized by ATR. Measures chase risk — values > 3.0 are extended.', formula: 'EMA10_Dist_N = ((Close - EMA10)/EMA10 × 100) / ATRP14' },
  { term: 'SMA150 Slope', definition: 'Rate of change of the primary anchor over 20 days. Thresholds: > +0.35% = rising, < -0.35% = falling.', formula: '(SMA150_today - SMA150_20d_ago) / SMA150_20d_ago × 100' },
  { term: 'Volume Ratio', definition: 'Current volume relative to 20-day average. Values > 1.5 confirm breakouts.', formula: 'Vol Ratio = Volume / Volume_Avg_20d' },
  { term: 'Mansfield RS', definition: "Stock's performance vs SPY over trailing year. Positive = outperforming the market.", formula: 'RS = Close/SPY_Close; Mansfield = (RS/SMA252(RS) - 1) × 100' },
  { term: 'Market Regime', definition: 'Market-wide risk state (R1–R5) from 6 macro inputs. Gates all downstream decisions.', formula: 'Composite = avg(6 scores); R1 ≤1.75, R2 ≤2.50, R3 ≤3.50, R4 ≤4.50, R5 >4.50' },
  { term: 'MACD', definition: 'Trend-following momentum indicator from two EMAs. Signal crossovers indicate momentum shifts.', formula: 'MACD = EMA(12) - EMA(26); Signal = EMA(9) of MACD' },
  { term: 'ADX / DI', definition: 'Trend strength (ADX > 25 = strong trend). +DI vs -DI shows direction.', formula: 'DX = |+DI - -DI|/(+DI + -DI) × 100; ADX = SMA(DX, 14)' },
  { term: 'TD Sequential', definition: 'DeMark exhaustion counter. 9-count setup suggests potential reversal.', formula: 'Buy: 9 consecutive closes below close 4 bars ago' },
];

type DeepDive = {
  title: string;
  sections: { heading: string; body: React.ReactNode }[];
};

const StageCycleDiagram: React.FC = () => (
  <Box position="relative" h="200px" w="100%" my={4} overflow="hidden">
    <svg viewBox="0 0 900 190" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="wave-stageCycle" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#9B2C2C" />
          <stop offset="8%" stopColor="#E53E3E" />
          <stop offset="15%" stopColor="#A0AEC0" />
          <stop offset="25%" stopColor="#718096" />
          <stop offset="35%" stopColor="#38A169" />
          <stop offset="50%" stopColor="#2F855A" />
          <stop offset="60%" stopColor="#D69E2E" />
          <stop offset="70%" stopColor="#DD6B20" />
          <stop offset="78%" stopColor="#C05621" />
          <stop offset="85%" stopColor="#E53E3E" />
          <stop offset="100%" stopColor="#9B2C2C" />
        </linearGradient>
      </defs>
      <path d="M 0 155 Q 50 155, 80 148 Q 120 140, 160 120 Q 200 100, 240 90 Q 280 85, 310 80 Q 370 55, 430 30 Q 470 18, 510 25 Q 560 35, 600 50 Q 640 65, 670 75 Q 700 85, 740 105 Q 780 130, 820 150 Q 860 165, 900 175" fill="none" stroke="url(#wave-stageCycle)" strokeWidth="3" />
      <line x1="0" y1="100" x2="900" y2="100" stroke="#718096" strokeWidth="1" strokeDasharray="6 3" opacity="0.4" />
      <text x="450" y="96" textAnchor="middle" fontSize="9" fill="#718096" opacity="0.6">SMA 150</text>
      <text x="40" y="175" textAnchor="middle" fontSize="11" fontWeight="600" fill="#9B2C2C">4C</text>
      <text x="100" y="160" textAnchor="middle" fontSize="11" fontWeight="600" fill="#E53E3E">4B</text>
      <text x="155" y="140" textAnchor="middle" fontSize="11" fontWeight="600" fill="#E53E3E">4A</text>
      <text x="220" y="110" textAnchor="middle" fontSize="11" fontWeight="600" fill="#A0AEC0">1A</text>
      <text x="280" y="95" textAnchor="middle" fontSize="11" fontWeight="600" fill="#718096">1B</text>
      <text x="350" y="65" textAnchor="middle" fontSize="11" fontWeight="600" fill="#38A169">2A</text>
      <text x="430" y="18" textAnchor="middle" fontSize="11" fontWeight="600" fill="#2F855A">2B</text>
      <text x="500" y="15" textAnchor="middle" fontSize="11" fontWeight="600" fill="#D69E2E">2C</text>
      <text x="610" y="40" textAnchor="middle" fontSize="11" fontWeight="600" fill="#DD6B20">3A</text>
      <text x="680" y="65" textAnchor="middle" fontSize="11" fontWeight="600" fill="#C05621">3B</text>
      <text x="760" y="105" textAnchor="middle" fontSize="11" fontWeight="600" fill="#E53E3E">4A</text>
    </svg>
  </Box>
);

const DEEP_DIVES: DeepDive[] = [
  {
    title: 'Stage Analysis (Oliver Kell / Weinstein)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <>
            <Text fontSize="sm" mb={2}>
              Stage Analysis here follows Oliver Kell&apos;s refinement of Stan Weinstein&apos;s four-stage market cycle model. The primary anchor shifts from the 30-week SMA (weekly) to <strong>SMA150 (daily)</strong>, enabling higher-resolution classification with <strong>10 sub-stages</strong>.
            </Text>
            <StageCycleDiagram />
          </>
        ),
      },
      {
        heading: '10 Sub-Stages',
        body: (
          <VStack align="stretch" gap={3}>
            <Text fontSize="sm" fontWeight="semibold">Decline Phase</Text>
            <SimpleGrid columns={{ base: 1, md: 3 }} gap={2}>
              <SubStageCard stage="4C" badgePalette="red">
                Deep decline. Price far below SMA150, slope strongly negative, Ext% &lt; -15%.
              </SubStageCard>
              <SubStageCard stage="4B" badgePalette="red">
                Active decline. Below SMA150, slope strongly negative.
              </SubStageCard>
              <SubStageCard stage="4A" badgePalette="red">
                Early decline. Below SMA150, slope non-positive, SMA50 falling.
              </SubStageCard>
            </SimpleGrid>
            <Text fontSize="sm" fontWeight="semibold">Basing Phase</Text>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={2}>
              <SubStageCard stage="1A" badgePalette="gray">
                Early base. Near SMA150 (&lt;5%), slope flat, still non-positive. Accumulation.
              </SubStageCard>
              <SubStageCard stage="1B" badgePalette="gray">
                Late base / breakout watch. Near SMA150, slope flat or gently rising. Watchlist stage.
              </SubStageCard>
            </SimpleGrid>
            <Text fontSize="sm" fontWeight="semibold">Advance Phase</Text>
            <SimpleGrid columns={{ base: 1, md: 3 }} gap={2}>
              <SubStageCard stage="2A" badgePalette="green">
                Early advance. Above SMA150, slope positive, Ext% ≤ 5%. Best risk/reward.
              </SubStageCard>
              <SubStageCard stage="2B" badgePalette="green">
                Confirmed advance. Slope strongly up (&gt;0.35%), Ext% 5–15%. Core holdings.
              </SubStageCard>
              <SubStageCard stage="2C" badgePalette="yellow">
                Extended advance. Slope up, Ext% &gt; 15% or ATRE_150 &gt; 6.0. Reduce risk.
              </SubStageCard>
            </SimpleGrid>
            <Text fontSize="sm" fontWeight="semibold">Distribution Phase</Text>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={2}>
              <SubStageCard stage="3A" badgePalette="orange">
                Early distribution. Above SMA150 but slope weakening. Tighten stops.
              </SubStageCard>
              <SubStageCard stage="3B" badgePalette="orange">
                Late distribution. Momentum fading, at risk of entering decline. Exit longs.
              </SubStageCard>
            </SimpleGrid>
          </VStack>
        ),
      },
      {
        heading: 'Classification Priority',
        body: (
          <VStack align="stretch" gap={2}>
            <Text fontSize="sm">Stages are classified in strict priority order (first match wins):</Text>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'4C → 4B → 4A → 1A → 1B → 2A → 2B → 2C → 3A → 3B\n\nKey thresholds:\n  SMA150 slope: ±0.35% (20-day lookback)\n  Extension %:  (Close - SMA150) / SMA150 × 100\n  SMA50 slope:  ±0.35% (10-day lookback)'}
            </Code>
          </VStack>
        ),
      },
      {
        heading: 'Post-Classification Overrides',
        body: (
          <VStack align="stretch" gap={2}>
            <Text fontSize="sm"><strong>ATRE Override:</strong> If ATRE_150 (ATR-extensions to SMA150) exceeds 6.0 while in Stage 2A or 2B, the stock is promoted to 2C. This catches names that are extended in ATR terms even if Ext% hasn&apos;t reached 15%.</Text>
            <Text fontSize="sm"><strong>RS Modifier:</strong> Stage 2B stocks with negative Mansfield RS are flagged as &quot;2B(RS-)&quot; — the trend is advancing but lagging the market. Lower conviction.</Text>
            <Text fontSize="sm"><strong>Breakout Confirmation (1B→2A):</strong> Requires: Close &gt; SMA150 AND Volume Ratio &gt; 1.5 AND EMA10 &gt; SMA21 &gt; SMA50.</Text>
          </VStack>
        ),
      },
      {
        heading: 'Color Legend',
        body: (
          <HStack gap={2} flexWrap="wrap">
            {[
              { stage: '1A', label: 'Early base', color: '#A0AEC0' },
              { stage: '1B', label: 'Late base', color: '#718096' },
              { stage: '2A', label: 'Early advance', color: '#38A169' },
              { stage: '2B', label: 'Confirmed', color: '#2F855A' },
              { stage: '2C', label: 'Extended', color: '#D69E2E' },
              { stage: '3A', label: 'Early distrib.', color: '#DD6B20' },
              { stage: '3B', label: 'Late distrib.', color: '#C05621' },
              { stage: '4A', label: 'Early decline', color: '#E53E3E' },
              { stage: '4B', label: 'Active decline', color: '#C53030' },
              { stage: '4C', label: 'Deep decline', color: '#9B2C2C' },
            ].map(({ stage, label, color }) => (
              <HStack key={stage} gap={1}>
                <Box w="12px" h="12px" borderRadius="sm" bg={color} flexShrink={0} />
                <Text fontSize="xs" fontWeight="semibold">{stage}</Text>
                <Text fontSize="xs" color="fg.muted">{label}</Text>
              </HStack>
            ))}
          </HStack>
        ),
      },
    ],
  },
  {
    title: 'Market Regime Engine (R1–R5)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <Text fontSize="sm">The Regime Engine is the <strong>outermost gate</strong> — a mandatory daily calculation that gates all downstream system behavior. It scores 6 macro inputs (1–5 each), computes a composite, and assigns one of 5 regime states.</Text>
        ),
      },
      {
        heading: '6 Daily Inputs',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm">1. <strong>VIX spot</strong> — 30-day implied volatility (fear gauge)</Text>
            <Text fontSize="sm">2. <strong>VIX3M/VIX ratio</strong> — term structure. &gt;1.0 = contango (calm), &lt;1.0 = backwardation (panic)</Text>
            <Text fontSize="sm">3. <strong>VVIX/VIX ratio</strong> — volatility-of-volatility. High = unstable vol regime</Text>
            <Text fontSize="sm">4. <strong>NH−NL</strong> — S&amp;P 500 new 52-week highs minus lows. Positive = healthy breadth</Text>
            <Text fontSize="sm">5. <strong>% above 200D</strong> — market breadth. &gt;70% = healthy, &lt;25% = broken</Text>
            <Text fontSize="sm">6. <strong>% above 50D</strong> — shorter-term breadth. &gt;75% = strong, &lt;25% = weak</Text>
          </VStack>
        ),
      },
      {
        heading: 'Regime States',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'Composite = average of 6 scores (1–5 each), rounded to nearest 0.5\n\nR1 (Bull):          1.0–1.75  │ Full exposure, all scan tiers\nR2 (Bull Extended): 1.75–2.50 │ Slightly reduced, Set 1-3\nR3 (Chop):          2.50–3.50 │ Half exposure, Set 1-2 + Short Set 1\nR4 (Bear Rally):    3.50–4.50 │ Minimal longs (Set 1 only), shorts active\nR5 (Bear):          4.50–5.0  │ No new longs, shorts + cash only'}
            </Code>
            <HStack gap={2} flexWrap="wrap" mt={2}>
              {[
                { r: 'R1', color: '#22C55E' },
                { r: 'R2', color: '#86EFAC' },
                { r: 'R3', color: '#EAB308' },
                { r: 'R4', color: '#F97316' },
                { r: 'R5', color: '#DC2626' },
              ].map(({ r, color }) => (
                <HStack key={r} gap={1}>
                  <Box w="12px" h="12px" borderRadius="sm" bg={color} flexShrink={0} />
                  <Text fontSize="xs" fontWeight="semibold">{r}</Text>
                </HStack>
              ))}
            </HStack>
          </VStack>
        ),
      },
      {
        heading: 'Portfolio Rules by Regime',
        body: (
          <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
            {'Regime │ Cash Floor │ Max Equity │ Multiplier │ Long Tiers    │ Short Tiers\n───────┼───────────┼───────────┼───────────┼──────────────┼────────────\n R1    │    5%     │   100%    │   1.0×    │ Set 1-2-3-4  │ None\n R2    │   10%     │    90%    │   0.75×   │ Set 1-2-3    │ None\n R3    │   25%     │    75%    │   0.5×    │ Set 1-2      │ Short Set 1\n R4    │   40%     │    60%    │   0.4×    │ Set 1        │ Short Set 1-2\n R5    │   60%     │    40%    │   0.25×   │ None         │ Short Set 1-2'}
          </Code>
        ),
      },
    ],
  },
  {
    title: 'Scan Overlay (Tier Assignment)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <Text fontSize="sm">The Scan Overlay assigns every stock to a tier based on 6 filters. Tiers are <strong>regime-gated</strong>: R1 sees all long tiers, R5 sees only short tiers. This prevents buying in bear markets.</Text>
        ),
      },
      {
        heading: 'Long Tiers',
        body: (
          <VStack align="stretch" gap={2}>
            <Text fontSize="sm"><strong>Set 1</strong> (highest conviction): Stage 2A/2B, RS &gt; 0, EMA10 Dist_N ≤ 2.0, ATRE pctile ≥ 70, Range ≥ 60%</Text>
            <Text fontSize="sm"><strong>Set 2</strong>: Stage 2A/2B/2C, RS &gt; -5, EMA10 Dist_N ≤ 3.0, Range ≥ 40%</Text>
            <Text fontSize="sm"><strong>Set 3</strong>: Stage 1B/2A/2B, EMA10 Dist_N ≤ 4.0</Text>
            <Text fontSize="sm"><strong>Set 4</strong> (marginal): Stage 1A/1B/2A, minimal filters</Text>
          </VStack>
        ),
      },
      {
        heading: 'Short Tiers',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>Short Set 1</strong>: Stage 4A/4B, RS &lt; 0, EMA10 Dist_N ≥ -2.0, Range ≤ 30%</Text>
            <Text fontSize="sm"><strong>Short Set 2</strong>: Stage 3B/4A/4B/4C, RS &lt; 5</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'Exit Cascade (9 Tiers)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <Text fontSize="sm">The Exit Cascade has <strong>9 independently-firing tiers</strong> for long positions and 4 for shorts. Each tier evaluates a different exit condition. The most aggressive (closest to exit) wins.</Text>
        ),
      },
      {
        heading: 'Base Exits (T1–T5)',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>T1 — Stop Loss:</strong> Hard stop at 2× ATR below entry.</Text>
            <Text fontSize="sm"><strong>T2 — Trailing Stop:</strong> Stage-based trail (1.5× ATR for 2A/2B, 2.0× for 2C, 1.0× for 3A+).</Text>
            <Text fontSize="sm"><strong>T3 — Stage Deterioration:</strong> 2B/2C→3A = reduce 50%. Any→4x = full exit.</Text>
            <Text fontSize="sm"><strong>T4 — Time-Based:</strong> 45+ days with &lt;5% gain = reduce. 90+ days negative = exit.</Text>
            <Text fontSize="sm"><strong>T5 — Profit Target:</strong> Ext% &gt;25% = reduce 25%. Ext% &gt;40% = reduce 50%.</Text>
          </VStack>
        ),
      },
      {
        heading: 'Regime Exits (T6–T9)',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>T6 — Regime Transition:</strong> R1/R2→R4/R5 = exit all. R1/R2→R3 = reduce 25%.</Text>
            <Text fontSize="sm"><strong>T7 — Regime Trail:</strong> Tighter stops in worse regimes (1.0× ATR in R3, 0.75× in R4, exit all in R5).</Text>
            <Text fontSize="sm"><strong>T8 — Regime Profit-Taking:</strong> R4 + Ext% &gt;10 = reduce 50%. R3 + Ext% &gt;15 = reduce 25%.</Text>
            <Text fontSize="sm"><strong>T9 — R5 Full Exit:</strong> R5 forces exit of all long positions regardless of stage or profit.</Text>
          </VStack>
        ),
      },
      {
        heading: 'Short Exits (S1–S4)',
        body: (
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm"><strong>S1 — Stage Improvement:</strong> Cover when stage improves to 1A/1B/2A/2B.</Text>
            <Text fontSize="sm"><strong>S2 — Regime Improvement:</strong> Cover when regime improves to R1/R2.</Text>
            <Text fontSize="sm"><strong>S3 — Vol Spike Cover:</strong> Ext% &lt; -25% = partial cover (reversal risk).</Text>
            <Text fontSize="sm"><strong>S4 — Profit Target:</strong> +20% P&amp;L = reduce 50%. +35% = full cover.</Text>
          </VStack>
        ),
      },
    ],
  },
  {
    title: 'Position Sizing (ATR-based)',
    sections: [
      {
        heading: 'Core Formula',
        body: (
          <VStack align="stretch" gap={2}>
            <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
              {'Full Position ($) = [Risk Budget / (ATR%14 × Stop Multiplier)] × Regime Multiplier\n\nThen apply Stage Cap:\n  Capped Position = Full Position × Stage_Cap[stage][regime]'}
            </Code>
            <Text fontSize="sm">The formula scales position size inversely to volatility (ATR%) and adjusts for market conditions (regime multiplier). A volatile stock gets a smaller position. A bearish regime shrinks all positions.</Text>
          </VStack>
        ),
      },
      {
        heading: 'Stage Caps',
        body: (
          <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
            {'Stage │  R1   │  R2   │  R3   │  R4   │  R5\n──────┼───────┼───────┼───────┼───────┼──────\n 1A   │  0%   │  0%   │  0%   │  0%   │  0%\n 1B   │  0%   │  0%   │  0%   │  0%   │  0%\n 2A   │ 75%   │ 50%   │ 50%   │ 33%   │  0%\n 2B   │ 100%  │ 100%  │ 75%   │  0%   │  0%\n 2C   │ 100%  │ 75%   │ 50%   │  0%   │  0%\n 3A   │ 50%   │ 25%   │  0%   │  0%   │  0%\n 3B+  │  0%   │  0%   │  0%   │  0%   │  0%'}
          </Code>
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
          <Text fontSize="sm">Measures performance relative to SPY over a trailing year. Positive = outperforming the market. Used as a scan filter and the RS modifier for Stage 2B.</Text>
        ),
      },
      {
        heading: 'How we calculate it',
        body: (
          <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
            {'Daily RS = Close / SPY_Close\n252-day SMA of RS\nMansfield RS% = (RS / SMA252(RS) - 1) × 100'}
          </Code>
        ),
      },
    ],
  },
  {
    title: 'Nightly Pipeline (10-Step Sequence)',
    sections: [
      {
        heading: 'Pipeline steps',
        body: (
          <Code fontSize="xs" p={3} borderRadius="md" display="block" whiteSpace="pre-wrap">
            {'Step 0:  REGIME — Load 6 macro inputs → composite → R1–R5 (runs FIRST)\nStep 1:  Compute MAs + ATRs\nStep 2:  Derive Ext%, ATRE, EMA10 Dist_N, slopes, ranges, Vol Ratio\nStep 3:  Classify 10 sub-stages (priority order)\nStep 4:  Post-classify: ATRE override, RS modifier, 2C override\nStep 5:  Scan: regime-gated tier assignment\nStep 6:  Patterns: 7 pattern triggers\nStep 7:  R/R: target/stop (regime-adjusted multipliers)\nStep 8:  Size: regime-adjusted full position × Stage Cap\nStep 9:  Exits: 9-tier cascade for open positions\nStep 10: Store all fields to MarketSnapshot + History'}
          </Code>
        ),
      },
    ],
  },
];

const GlossaryCard: React.FC<{ entry: GlossaryEntry }> = ({ entry }) => (
  <Box borderWidth="1px" borderColor="border.subtle" borderRadius="lg" p={4} bg="bg.card">
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
      <Button variant="ghost" w="100%" justifyContent="flex-start" px={4} py={3} borderRadius={0} onClick={() => setOpen((v) => !v)} _hover={{ bg: 'bg.muted' }}>
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
                <Text fontSize="xs" fontWeight="bold" textTransform="uppercase" letterSpacing="wide" color="fg.muted" mb={2}>{s.heading}</Text>
                {s.body}
              </Box>
            ))}
          </VStack>
        </Collapsible.Content>
      </Collapsible.Root>
    </Box>
  );
};

type TabId = 'glossary' | 'deep-dives';

const MarketEducation: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('deep-dives');
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
        <Heading size="md">Stage Analysis — Education</Heading>
        <Text color="fg.muted" fontSize="sm" mt={1}>
          Oliver Kell&apos;s refinement of Weinstein Stage Analysis. SMA150 anchor, 10 sub-stages, Market Regime Engine, Scan Overlay, Exit Cascade, and ATR-based Position Sizing.
        </Text>
      </Box>

      <HStack gap={1} borderBottomWidth="1px" borderColor="border.subtle" pb={0} mb={4}>
        {(['deep-dives', 'glossary'] as TabId[]).map((tab) => {
          const isActive = activeTab === tab;
          return (
            <Button
              key={tab}
              size="sm"
              variant={isActive ? 'solid' : 'ghost'}
              bg={isActive ? 'amber.500' : undefined}
              color={isActive ? 'white' : undefined}
              _hover={isActive ? { bg: 'amber.400' } : undefined}
              onClick={() => setActiveTab(tab)}
              borderBottomRadius={0}
            >
              {tab === 'glossary' ? 'Glossary' : 'System Deep-Dives'}
            </Button>
          );
        })}
      </HStack>

      {activeTab === 'glossary' && (
        <Box>
          <HStack mb={4} maxW="400px">
            <FiSearch />
            <Input placeholder="Search terms..." size="sm" value={search} onChange={(e) => setSearch(e.target.value)} />
          </HStack>
          {filteredGlossary.length === 0 ? (
            <Text fontSize="sm" color="fg.muted">No terms match &quot;{search}&quot;.</Text>
          ) : (
            <Box display="grid" gridTemplateColumns={{ base: '1fr', md: '1fr 1fr', xl: '1fr 1fr 1fr' }} gap={3}>
              {filteredGlossary.map((entry) => (
                <GlossaryCard key={entry.term} entry={entry} />
              ))}
            </Box>
          )}
        </Box>
      )}

      {activeTab === 'deep-dives' && (
        <VStack align="stretch" gap={3}>
          {DEEP_DIVES.map((dive) => (
            <DeepDiveSection key={dive.title} dive={dive} />
          ))}
        </VStack>
      )}

      <Box mt={8} pt={4} borderTopWidth="1px" borderColor="border.subtle">
        <Text fontSize="xs" color="fg.subtle" fontStyle="italic">
          Reflects the same calculations as the backend. Source: backend/services/market/indicator_engine.py
        </Text>
      </Box>
    </Box>
  );
};

export default MarketEducation;
