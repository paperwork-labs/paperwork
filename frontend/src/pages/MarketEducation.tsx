import React, { useState, useMemo } from 'react';
import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronDown, ChevronRight, Search } from 'lucide-react';

import { STAGE_HEX } from '../constants/chart';
import { InteractiveStageExplorer } from '@/components/education/StageChartExample';
import { useColorMode } from '../theme/colorMode';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Page, PageHeader } from '@/components/ui/Page';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

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

  const paletteClass =
    badgePalette === 'red'
      ? 'bg-destructive/10 text-destructive'
      : badgePalette === 'green'
        ? 'border-transparent bg-[rgb(var(--status-success)/0.12)] text-[rgb(var(--status-success)/1)]'
        : badgePalette === 'yellow'
          ? 'border-transparent bg-amber-500/15 text-amber-700 dark:text-amber-400'
          : badgePalette === 'orange'
            ? 'border-transparent bg-orange-500/15 text-orange-700 dark:text-orange-400'
            : 'bg-secondary text-secondary-foreground';

  return (
    <div
      className="rounded-md border border-border border-l-[3px] p-3"
      style={{ borderLeftColor: hex, backgroundColor: bgMixed }}
    >
      <Badge variant="secondary" className={cn('mb-1 font-medium', paletteClass)}>
        {stage}
      </Badge>
      <p className="text-xs text-muted-foreground">{children}</p>
    </div>
  );
};

const GLOSSARY: GlossaryEntry[] = [
  { term: 'SMA (Simple Moving Average)', definition: 'Arithmetic mean of price over N periods. Key SMAs: 21, 50, 100, 150 (primary stage anchor), 200.', formula: 'SMA(n) = (P₁ + P₂ + … + Pₙ) / n' },
  { term: 'EMA (Exponential Moving Average)', definition: 'Weighted average giving more weight to recent prices. Key EMAs: 10 (short-term trend), 21, 200.', formula: 'EMA = Price × k + EMA(prev) × (1 - k), where k = 2/(n+1)' },
  { term: 'RSI (Relative Strength Index)', definition: 'Momentum oscillator (0–100) using Wilder smoothing. Above 70 = overbought, below 30 = oversold.', formula: 'RS = Wilder Avg Gain / Wilder Avg Loss; RSI = 100 - 100/(1+RS)' },
  { term: 'ATR (Average True Range)', definition: 'Volatility measure — average range of price movement. ATR%14 normalizes across price levels.', formula: "TR = max(H-L, |H-PrevC|, |L-PrevC|); ATR uses Wilder's smoothing: seed with SMA of first 14 TRs, then ATR = (prev_ATR x 13 + TR) / 14" },
  { term: 'ATRP (ATR Percentage)', definition: 'ATR as a % of current price. A $10 stock with ATR $0.50 and a $500 stock with ATR $25 both have ATRP 5%.', formula: 'ATRP = (ATR / Price) × 100' },
  { term: 'Extension % (Ext%)', definition: 'How far price has moved from SMA150 — the primary distance metric in Stage Analysis.', formula: 'Ext% = (Close - SMA150) / SMA150 × 100' },
  { term: 'ATRE (ATR Extensions)', definition: 'Price distance from key MAs measured in ATRs. ATRE_150 > 6.0 triggers the 2C override.', formula: 'ATRE_150 = (Close - SMA150) / ATR14' },
  { term: 'EMA10 Distance (Normalized)', definition: 'How far price is from EMA10, normalized by ATR. Measures chase risk — values > 3.0 are extended.', formula: 'EMA10_Dist_N = ((Close - EMA10)/EMA10 × 100) / ATRP14' },
  { term: 'SMA150 Slope', definition: 'Rate of change of the primary anchor over 20 days. Thresholds: > +0.35% = rising, < -0.35% = falling.', formula: '(SMA150_today - SMA150_20d_ago) / SMA150_20d_ago × 100' },
  { term: 'Volume Ratio', definition: 'Current volume relative to 20-day average. Values > 1.5 confirm breakouts.', formula: 'Vol Ratio = Volume / Volume_Avg_20d' },
  { term: 'Mansfield RS', definition: "Stock's performance vs SPY over trailing year. Positive = outperforming the market.", formula: 'RS = Close/SPY_Close; Mansfield = (RS/SMA252(RS) - 1) × 100' },
  { term: 'Market Regime', definition: 'Market-wide risk state (R1–R5) from 6 macro inputs. Gates all downstream decisions.', formula: 'Composite = avg(6 scores); R1 ≤1.75, R2 ≤2.50, R3 ≤3.50, R4 ≤4.50, R5 >4.50' },
  { term: 'MACD', definition: 'Trend-following momentum indicator from two EMAs. Signal crossovers indicate momentum shifts.', formula: 'MACD = EMA(12) - EMA(26); Signal = EMA(9) of MACD' },
  { term: 'ADX / DI', definition: 'Trend strength (ADX > 25 = strong trend). +DI vs -DI shows direction.', formula: "DX = |+DI - -DI|/(+DI + -DI) × 100; ADX uses Wilder's smoothing: seed with SMA of first 14 DX values, then ADX = (prev_ADX x 13 + DX) / 14" },
  { term: 'Bollinger Bands', definition: 'Upper and lower bands at 2 population standard deviations from SMA(20). Squeeze (bands inside Keltner) indicates low volatility.', formula: 'Upper = SMA20 + 2*std(Close,20,ddof=0); Lower = SMA20 - 2*std' },
  { term: 'Keltner Channels', definition: 'Volatility envelope using EMA and ATR. Used with Bollinger Bands to detect TTM Squeeze.', formula: 'Upper = EMA20 + 1.5*ATR10; Lower = EMA20 - 1.5*ATR10' },
  { term: 'TTM Squeeze', definition: 'When Bollinger Bands contract inside Keltner Channels, volatility is compressed. Momentum direction on release signals the breakout direction.', formula: 'Squeeze On = BB_lower > KC_lower AND BB_upper < KC_upper' },
  { term: 'Stochastic RSI', definition: 'Applies stochastic formula to RSI values. More sensitive than raw RSI for identifying overbought/oversold conditions.', formula: 'StochRSI = (RSI - min(RSI,14)) / (max(RSI,14) - min(RSI,14))' },
  { term: 'MA Bucket', definition: 'Classification of moving average alignment: LEADING (EMA10 > SMA21 > SMA50 > SMA150), LAGGING (reverse), or NEUTRAL (mixed).', formula: null },
  { term: 'Performance Windows', definition: 'Percentage returns calculated over 1d, 3d, 5d, 20d, 60d, 120d, and 252d windows, plus MTD, QTD, and YTD.', formula: 'Perf = (Close / Close_N_bars_ago - 1) x 100' },
  { term: 'TD Sequential', definition: 'DeMark exhaustion counter. 9-count setup suggests potential reversal. Counter resets to 0 after reaching a 9-count setup.', formula: 'Buy: 9 consecutive closes below close 4 bars ago' },
];

type DeepDive = {
  title: string;
  sections: { heading: string; body: React.ReactNode }[];
};

const StageCycleDiagram: React.FC = () => (
  <div className="relative my-4 h-[200px] w-full overflow-hidden">
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
      <text x="760" y="105" textAnchor="middle" fontSize="11" fontWeight="600" fill="#E53E3E">4C</text>
    </svg>
  </div>
);

const codeBlock = (s: string) => (
  <pre className="block whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">{s}</pre>
);

const DEEP_DIVES: DeepDive[] = [
  {
    title: 'Stage Analysis (Oliver Kell / Weinstein)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <>
            <p className="mb-2 text-sm">
              Stage Analysis here follows Oliver Kell&apos;s refinement of Stan Weinstein&apos;s four-stage market cycle model. The primary anchor shifts from the 30-week SMA (weekly) to <strong>SMA150 (daily)</strong>, enabling higher-resolution classification with <strong>10 sub-stages</strong>.
            </p>
            <StageCycleDiagram />
          </>
        ),
      },
      {
        heading: '10 Sub-Stages',
        body: (
          <div className="flex flex-col gap-3">
            <p className="text-sm font-semibold">Decline Phase</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
              <SubStageCard stage="4C" badgePalette="red">
                Deep decline. Price far below SMA150, slope strongly negative, Ext% &lt; -15%.
              </SubStageCard>
              <SubStageCard stage="4B" badgePalette="red">
                Active decline. Below SMA150, slope strongly negative.
              </SubStageCard>
              <SubStageCard stage="4A" badgePalette="red">
                Early decline. Below SMA150, slope non-positive, SMA50 falling.
              </SubStageCard>
            </div>
            <p className="text-sm font-semibold">Basing Phase</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <SubStageCard stage="1A" badgePalette="gray">
                Early base. Near SMA150 (&lt;5%), slope flat, still non-positive. Accumulation.
              </SubStageCard>
              <SubStageCard stage="1B" badgePalette="gray">
                Late base / breakout watch. Near SMA150, slope flat or gently rising. Watchlist stage.
              </SubStageCard>
            </div>
            <p className="text-sm font-semibold">Advance Phase</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
              <SubStageCard stage="2A" badgePalette="green">
                Early advance. Above SMA150, slope positive, Ext% ≤ 5%. Best risk/reward.
              </SubStageCard>
              <SubStageCard stage="2B" badgePalette="green">
                Confirmed advance. Slope strongly up (&gt;0.35%), Ext% 5–15%. Core holdings.
              </SubStageCard>
              <SubStageCard stage="2C" badgePalette="yellow">
                Extended advance. Slope up, Ext% &gt; 15% or ATRE_150 &gt; 6.0. Reduce risk.
              </SubStageCard>
            </div>
            <p className="text-sm font-semibold">Distribution Phase</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <SubStageCard stage="3A" badgePalette="orange">
                Early distribution. Above SMA150 but slope weakening. Tighten stops.
              </SubStageCard>
              <SubStageCard stage="3B" badgePalette="orange">
                Late distribution. Momentum fading, at risk of entering decline. Exit longs.
              </SubStageCard>
            </div>
            <InteractiveStageExplorer className="mt-4" />
          </div>
        ),
      },
      {
        heading: 'Classification Priority',
        body: (
          <div className="flex flex-col gap-2">
            <p className="text-sm">Stages are classified in strict priority order (first match wins):</p>
            {codeBlock(
              '4C → 4B → 4A → 1A → 1B → 2A → 2B → 2C → 3A → 3B\n\nKey thresholds:\n  SMA150 slope: ±0.35% (20-day lookback)\n  Extension %:  (Close - SMA150) / SMA150 × 100\n  SMA50 slope:  ±0.35% (10-day lookback)',
            )}
          </div>
        ),
      },
      {
        heading: 'Post-Classification Overrides',
        body: (
          <div className="flex flex-col gap-2">
            <p className="text-sm"><strong>ATRE Override:</strong> If ATRE_150 (ATR-extensions to SMA150) exceeds 6.0 while in Stage 2A or 2B, the stock is promoted to 2C. This catches names that are extended in ATR terms even if Ext% hasn&apos;t reached 15%.</p>
            <p className="text-sm"><strong>RS Modifier:</strong> Stage 2B stocks with negative Mansfield RS are flagged as &quot;2B(RS-)&quot; — the trend is advancing but lagging the market. Lower conviction.</p>
            <p className="text-sm"><strong>Breakout Confirmation (1B→2A):</strong> Requires: Close &gt; SMA150 AND Volume Ratio &gt; 1.5 AND EMA10 &gt; SMA21 &gt; SMA50.</p>
          </div>
        ),
      },
      {
        heading: 'Color Legend',
        body: (
          <div className="flex flex-wrap gap-2">
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
              <div key={stage} className="flex items-center gap-1">
                <div className="size-3 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
                <span className="text-xs font-semibold">{stage}</span>
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
            ))}
          </div>
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
          <p className="text-sm">The Regime Engine is the <strong>outermost gate</strong> — a mandatory daily calculation that gates all downstream system behavior. It scores 6 macro inputs (1–5 each), computes a composite, and assigns one of 5 regime states.</p>
        ),
      },
      {
        heading: '6 Daily Inputs',
        body: (
          <div className="flex flex-col gap-1">
            <p className="text-sm">1. <strong>VIX spot</strong> — 30-day implied volatility (fear gauge)</p>
            <p className="text-sm">2. <strong>VIX3M/VIX ratio</strong> — term structure. &gt;1.0 = contango (calm), &lt;1.0 = backwardation (panic)</p>
            <p className="text-sm">3. <strong>VVIX/VIX ratio</strong> — volatility-of-volatility. High = unstable vol regime</p>
            <p className="text-sm">4. <strong>NH−NL</strong> — S&amp;P 500 new 52-week highs minus lows. Positive = healthy breadth</p>
            <p className="text-sm">5. <strong>% above 200D</strong> — market breadth. &gt;70% = healthy, &lt;25% = broken</p>
            <p className="text-sm">6. <strong>% above 50D</strong> — shorter-term breadth. &gt;75% = strong, &lt;25% = weak</p>
          </div>
        ),
      },
      {
        heading: 'Regime States',
        body: (
          <div className="flex flex-col gap-2">
            {codeBlock(
              'Composite = average of 6 scores (1–5 each), rounded to nearest 0.5\n\nR1 (Bull):          1.0–1.75  │ Full exposure, all scan tiers\nR2 (Bull Extended): 1.75–2.50 │ Slightly reduced, Elite/Standard/Base\nR3 (Chop):          2.50–3.50 │ Half exposure, Elite/Standard + Breakdown Elite\nR4 (Bear Rally):    3.50–4.50 │ Minimal longs (Elite only), shorts active\nR5 (Bear):          4.50–5.0  │ No new longs, shorts + cash only',
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              {[
                { r: 'R1', color: '#22C55E' },
                { r: 'R2', color: '#86EFAC' },
                { r: 'R3', color: '#EAB308' },
                { r: 'R4', color: '#F97316' },
                { r: 'R5', color: '#DC2626' },
              ].map(({ r, color }) => (
                <div key={r} className="flex items-center gap-1">
                  <div className="size-3 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
                  <span className="text-xs font-semibold">{r}</span>
                </div>
              ))}
            </div>
          </div>
        ),
      },
      {
        heading: 'Portfolio Rules by Regime',
        body: codeBlock(
          'Regime │ Cash Floor │ Max Equity │ Multiplier │ Long Tiers                        │ Short Tiers\n───────┼───────────┼───────────┼───────────┼──────────────────────────────────┼──────────────────\n R1    │    5%     │   100%    │   1.0×    │ Elite/Standard/Base/Speculative  │ None\n R2    │   10%     │    90%    │   0.75×   │ Elite/Standard/Base              │ None\n R3    │   25%     │    75%    │   0.5×    │ Elite/Standard                   │ Breakdown Elite\n R4    │   40%     │    60%    │   0.4×    │ Elite                            │ Breakdown Elite/Std\n R5    │   60%     │    40%    │   0.25×   │ None                             │ Breakdown Elite/Std',
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
          <p className="text-sm">The Scan Overlay assigns every stock to a tier based on 6 filters. Tiers are <strong>regime-gated</strong>: R1 sees all long tiers, R5 sees only short tiers. This prevents buying in bear markets.</p>
        ),
      },
      {
        heading: 'Long Tiers',
        body: (
          <div className="flex flex-col gap-2">
            <p className="text-sm"><strong>Breakout Elite</strong> (highest conviction): Stage 2A/2B, RS &gt; 0, EMA10 Dist_N ≤ 2.0, ATRE pctile ≥ 70, Range ≥ 60%</p>
            <p className="text-sm"><strong>Breakout Standard</strong>: Stage 2A/2B/2C, RS &gt; -5, EMA10 Dist_N ≤ 3.0, Range ≥ 40%</p>
            <p className="text-sm"><strong>Early Base</strong>: Stage 1B/2A/2B, EMA10 Dist_N ≤ 4.0</p>
            <p className="text-sm"><strong>Speculative</strong> (marginal): Stage 1A/1B/2A, minimal filters</p>
          </div>
        ),
      },
      {
        heading: 'Short Tiers',
        body: (
          <div className="flex flex-col gap-1">
            <p className="text-sm"><strong>Breakdown Elite</strong>: Stage 4A/4B, RS &lt; 0, EMA10 Dist_N ≥ -2.0, Range ≤ 30%</p>
            <p className="text-sm"><strong>Breakdown Standard</strong>: Stage 3B/4A/4B/4C, RS &lt; 5</p>
          </div>
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
          <p className="text-sm">The Exit Cascade has <strong>9 independently-firing tiers</strong> for long positions and 4 for shorts. Each tier evaluates a different exit condition. The most aggressive (closest to exit) wins.</p>
        ),
      },
      {
        heading: 'Base Exits (T1–T5)',
        body: (
          <div className="flex flex-col gap-1">
            <p className="text-sm"><strong>T1 — Stop Loss:</strong> Hard stop at 2× ATR below entry.</p>
            <p className="text-sm"><strong>T2 — Trailing Stop:</strong> Stage-based trail (1.5× ATR for 2A/2B, 2.0× for 2C, 1.0× for 3A+). The effective ATR multiplier is tightened or widened by regime (e.g. R3/R4/R5 pull it down) and by volatility (ATRP-based adjustments).</p>
            <p className="text-sm"><strong>T3 — Stage Deterioration:</strong> 2B/2C→3A = reduce 50%. Reaching Stage 3B = full exit (late distribution). Any→4x = full exit.</p>
            <p className="text-sm"><strong>T4 — Time-Based:</strong> Uses <strong>days held</strong> in the position (since open), not time in the current stage: 45+ days held with &lt;5% gain = reduce; 90+ days held and negative = exit.</p>
            <p className="text-sm"><strong>T5 — Profit Target:</strong> Ext% &gt;25% = reduce 25%. Ext% &gt;40% = reduce 50%.</p>
          </div>
        ),
      },
      {
        heading: 'Regime Exits (T6–T9)',
        body: (
          <div className="flex flex-col gap-1">
            <p className="text-sm"><strong>T6 — Regime Transition:</strong> R1/R2→R4/R5 = exit all. R1/R2→R3 = reduce 25%.</p>
            <p className="text-sm"><strong>T7 — Regime Trail:</strong> Tighter stops in worse regimes (1.0× ATR in R3, 0.75× in R4, exit all in R5).</p>
            <p className="text-sm"><strong>T8 — Regime Profit-Taking:</strong> R4 + Ext% &gt;10 = reduce 50%. R3 + Ext% &gt;15 = reduce 25%.</p>
            <p className="text-sm"><strong>T9 — R5 Full Exit:</strong> R5 forces exit of all long positions regardless of stage or profit.</p>
          </div>
        ),
      },
      {
        heading: 'Short Exits (S1–S4)',
        body: (
          <div className="flex flex-col gap-1">
            <p className="text-sm"><strong>S1 — Stage Improvement:</strong> Cover when stage improves to 1A/1B/2A/2B.</p>
            <p className="text-sm"><strong>S2 — Regime Improvement:</strong> Cover when regime improves to R1/R2.</p>
            <p className="text-sm"><strong>S3 — Vol Spike Cover:</strong> Ext% &lt; -25% = partial cover (reversal risk).</p>
            <p className="text-sm"><strong>S4 — Profit Target:</strong> Short P&amp;L above +35% triggers full cover; above +20% (and ≤35%) triggers reduce 50%.</p>
          </div>
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
          <div className="flex flex-col gap-2">
            {codeBlock(
              'Risk budget ($) = account_equity × risk_per_trade_pct\nATR_14 = 14-period ATR in dollars per share (not a %)\n\nShares sized to risk (conceptual, before regime/stage caps):\n  shares ≈ risk_budget / (ATR_14 × stop_multiplier)\n\nBackend (risk_gate.compute_position_size) is equivalent: it uses ATR%14\nwhere (ATR%14 / 100) = ATR_14 / price, so:\n  Full Position ($) = [risk_budget / ((ATR%14 / 100) × stop_multiplier)] × regime_multiplier\n\nThen apply Stage Cap:\n  Capped Position = Full Position × Stage_Cap[stage][regime]\n  shares = floor(capped_position_dollars / price)',
            )}
            <p className="text-sm">Risk per share at the stop is proportional to <strong>ATR in dollars</strong> times the stop multiplier; the implementation divides by ATR% (i.e. ATR/price) and multiplies by price in the same step. Regime and stage caps then shrink the dollar allocation before converting to whole shares.</p>
          </div>
        ),
      },
      {
        heading: 'Stage Caps',
        body: codeBlock(
          'Stage │  R1   │  R2   │  R3   │  R4   │  R5\n──────┼───────┼───────┼───────┼───────┼──────\n 1A   │  0%   │  0%   │  0%   │  0%   │  0%\n 1B   │  0%   │  0%   │  0%   │  0%   │  0%\n 2A   │ 75%   │ 50%   │ 50%   │ 33%   │  0%\n 2B   │ 100%  │ 100%  │ 75%   │  0%   │  0%\n 2C   │ 100%  │ 75%   │ 50%   │  0%   │  0%\n 3A   │ 50%   │ 25%   │  0%   │  0%   │  0%\n 3B+  │  0%   │  0%   │  0%   │  0%   │  0%',
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
          <p className="text-sm">Measures performance relative to SPY over a trailing year. Positive = outperforming the market. Used as a scan filter and the RS modifier for Stage 2B.</p>
        ),
      },
      {
        heading: 'How we calculate it',
        body: codeBlock(
          'Daily RS = Close / SPY_Close\n252-day SMA of RS\nMansfield RS% = (RS / SMA252(RS) - 1) × 100',
        ),
      },
    ],
  },
  {
    title: 'Nightly Pipeline (10-Step Sequence)',
    sections: [
      {
        heading: 'Pipeline steps',
        body: codeBlock(
          'Step 0:  REGIME — Load 6 macro inputs → composite → R1–R5 (runs FIRST)\nStep 1:  Compute MAs + ATRs\nStep 2:  Derive Ext%, ATRE, EMA10 Dist_N, slopes, ranges, Vol Ratio\nStep 3:  Classify 10 sub-stages (priority order)\nStep 4:  Post-classify: ATRE override (2A/2B with ATRE_150 > 6 → 2C extended; not a separate pipeline step), RS modifier\nStep 5:  Scan: regime-gated tier assignment\nStep 6:  Patterns: 7 pattern triggers\nStep 7:  R/R: target/stop (regime-adjusted multipliers)\nStep 8:  Size: regime-adjusted full position × Stage Cap\nStep 9:  Exits: 9-tier cascade for open positions\nStep 10: Store all fields to MarketSnapshot + History',
        ),
      },
    ],
  },
  {
    title: 'Action Labels (Signal Classification)',
    sections: [
      {
        heading: 'Overview',
        body: (
          <p className="text-sm">
            Each snapshot gets an <strong>action label</strong> after regime-gated scan tier assignment. Labels summarize how the system reads stage + tier + regime together. Breakdown tiers map to <strong>SHORT</strong> (separate from the long-oriented labels below).
          </p>
        ),
      },
      {
        heading: 'Long-oriented labels',
        body: (
          <div className="flex flex-col gap-2">
            <p className="text-sm">
              <strong>BUY</strong> — Assigned when the stock is in <strong>Breakout Elite</strong>, or in <strong>Breakout Standard</strong> while regime is <strong>R1 or R2</strong> (strong/extended bull). Highest conviction new-long signal from the scan overlay.
            </p>
            <p className="text-sm">
              <strong>WATCH</strong> — <strong>Breakout Standard</strong> in <strong>R3+</strong> (chop or worse): setup exists but regime caps aggression. Also <strong>Early Base</strong>, <strong>Speculative</strong>, and Stage <strong>1A/1B</strong>. If there is <strong>no scan tier</strong> but stage is <strong>2A/2B</strong>, label is WATCH in <strong>R1/R2</strong> (building or holding context without a tier match).
            </p>
            <p className="text-sm">
              <strong>HOLD</strong> — Stage <strong>2C</strong> (extended advance: maintain with tighter risk). If stage is <strong>2A/2B</strong> with <strong>no tier</strong>, label is HOLD in <strong>R3 or R4</strong> (chop / bear rally: do not add; protect positions).
            </p>
            <p className="text-sm">
              <strong>REDUCE</strong> — Stage <strong>3A or 3B</strong> when not captured by a short tier: distribution / late advance — trim or exit longs per playbook.
            </p>
            <p className="text-sm">
              <strong>AVOID</strong> — Stage <strong>4A/4B/4C</strong> (decline), or any unmatched fallback: not a long candidate.
            </p>
          </div>
        ),
      },
      {
        heading: 'Evaluation order',
        body: (
          <p className="text-sm">
            The backend evaluates <strong>short tiers first</strong>, then long tiers (Elite → Standard → Early Base → Speculative), then <strong>stage-only</strong> rules if no tier applies. Regime gates which tiers exist at all; the label refines the message once tier and stage are known. Implementation: <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">derive_action_label</code> in <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">scan_engine.py</code>.
          </p>
        ),
      },
    ],
  },
];

const GlossaryCard: React.FC<{ entry: GlossaryEntry }> = ({ entry }) => (
  <Card className="gap-0 py-4 shadow-xs ring-1 ring-foreground/10">
    <CardContent className="flex flex-col gap-2">
      <p className="text-sm font-semibold">{entry.term}</p>
      <p className={cn('text-sm text-muted-foreground', entry.formula && 'mb-2')}>{entry.definition}</p>
      {entry.formula ? (
        <pre className="mt-1 block whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-xs">{entry.formula}</pre>
      ) : null}
    </CardContent>
  </Card>
);

const DeepDiveSection: React.FC<{ dive: DeepDive }> = ({ dive }) => {
  const [open, setOpen] = useState(false);
  return (
    <Card className="gap-0 overflow-hidden py-0 shadow-xs ring-1 ring-foreground/10">
      <Collapsible.Root open={open} onOpenChange={setOpen}>
        <Collapsible.Trigger
          type="button"
          className="flex w-full cursor-pointer select-none items-center gap-2 rounded-none border-0 bg-transparent px-4 py-3 text-left outline-none hover:bg-muted/80 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          {open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
          <span className="text-sm font-semibold">{dive.title}</span>
        </Collapsible.Trigger>
        <Collapsible.Content>
          <div className="flex flex-col gap-4 px-5 pt-2 pb-5">
            {dive.sections.map((s) => (
              <div key={s.heading}>
                <p className="mb-2 text-xs font-bold tracking-wide text-muted-foreground uppercase">{s.heading}</p>
                {s.body}
              </div>
            ))}
          </div>
        </Collapsible.Content>
      </Collapsible.Root>
    </Card>
  );
};

const MarketEducation: React.FC = () => {
  const [search, setSearch] = useState('');

  const filteredGlossary = useMemo(() => {
    if (!search.trim()) return GLOSSARY;
    const q = search.toLowerCase();
    return GLOSSARY.filter(
      (g) => g.term.toLowerCase().includes(q) || g.definition.toLowerCase().includes(q),
    );
  }, [search]);

  return (
    <Page>
      <PageHeader
        title="Stage Analysis — Education"
        subtitle="Oliver Kell&apos;s refinement of Weinstein Stage Analysis. SMA150 anchor, 10 sub-stages, Market Regime Engine, Scan Overlay, Exit Cascade, and ATR-based Position Sizing."
      />

      <Tabs defaultValue="deep-dives" className="w-full">
        <TabsList variant="line" className="mb-4 w-full justify-start sm:w-auto">
          <TabsTrigger value="deep-dives">System Deep-Dives</TabsTrigger>
          <TabsTrigger value="glossary">Glossary</TabsTrigger>
        </TabsList>

        <TabsContent value="glossary" className="mt-0">
          <div className="mb-4 flex max-w-[400px] items-center gap-2">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <Input
              placeholder="Search terms..."
              className="h-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {filteredGlossary.length === 0 ? (
            <p className="text-sm text-muted-foreground">No terms match &quot;{search}&quot;.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filteredGlossary.map((entry) => (
                <GlossaryCard key={entry.term} entry={entry} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="deep-dives" className="mt-0">
          <div className="flex flex-col gap-3">
            {DEEP_DIVES.map((dive) => (
              <DeepDiveSection key={dive.title} dive={dive} />
            ))}
          </div>
        </TabsContent>
      </Tabs>

      <div className="mt-8 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground italic">
          Reflects the same calculations as the backend. Stage classification: backend/services/market/stage_classifier.py; indicators: backend/services/market/indicator_engine.py
        </p>
      </div>
    </Page>
  );
};

export default MarketEducation;
