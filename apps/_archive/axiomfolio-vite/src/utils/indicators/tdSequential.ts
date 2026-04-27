import type { OHLCBar } from './trendLines';
import { TD_HEX } from '../../constants/chart';

export interface TDLabel {
  time: number;
  value: number;
  text: string;
  position: 'above' | 'below';
  color: string;
  size: 'small' | 'tiny';
}

export function computeTDSequential(bars: OHLCBar[], colorMode: 'light' | 'dark' = 'dark'): TDLabel[] {
  const idx = colorMode === 'dark' ? 1 : 0;
  const COLOR_SETUP = TD_HEX.setup[idx];
  const COLOR_PERFECT = TD_HEX.perfect[idx];
  const COLOR_COUNTDOWN = TD_HEX.countdown[idx];
  if (bars.length < 5) return [];

  const labels: TDLabel[] = [];
  let buySetup = 0;
  let sellSetup = 0;
  let buyComplete = false;
  let sellComplete = false;
  let buyCountdown = 0;
  let sellCountdown = 0;

  for (let i = 4; i < bars.length; i++) {
    const close = bars[i].close;
    const close4 = bars[i - 4].close;

    // Buy setup: close < close[4]
    if (close < close4) {
      buySetup++;
      sellSetup = 0;
      sellComplete = false;

      if (buySetup >= 9) {
        const isPerfect =
          bars[i].low < bars[i - 2].low &&
          bars[i].low < bars[i - 3].low &&
          bars[i - 1].low < bars[i - 2].low &&
          bars[i - 1].low < bars[i - 3].low;

        labels.push({
          time: bars[i].time,
          value: bars[i].low,
          text: String(buySetup),
          position: 'below',
          color: isPerfect ? COLOR_PERFECT : COLOR_SETUP,
          size: 'small',
        });

        buyComplete = true;
        buySetup = 0;
      } else {
        labels.push({
          time: bars[i].time,
          value: bars[i].low,
          text: String(buySetup),
          position: 'below',
          color: COLOR_SETUP,
          size: 'small',
        });
      }
    }

    // Sell setup: close > close[4]
    if (close > close4) {
      sellSetup++;
      buySetup = 0;
      buyComplete = false;

      if (sellSetup >= 9) {
        const isPerfect =
          bars[i].high > bars[i - 2].high &&
          bars[i].high > bars[i - 3].high &&
          bars[i - 1].high > bars[i - 2].high &&
          bars[i - 1].high > bars[i - 3].high;

        labels.push({
          time: bars[i].time,
          value: bars[i].high,
          text: String(sellSetup),
          position: 'above',
          color: isPerfect ? COLOR_PERFECT : COLOR_SETUP,
          size: 'small',
        });

        sellComplete = true;
        sellSetup = 0;
      } else {
        labels.push({
          time: bars[i].time,
          value: bars[i].high,
          text: String(sellSetup),
          position: 'above',
          color: COLOR_SETUP,
          size: 'small',
        });
      }
    }

    // Buy countdown
    if (buyComplete && i >= 2 && close <= bars[i - 2].low) {
      buyCountdown++;
      labels.push({
        time: bars[i].time,
        value: bars[i].low,
        text: `+${buyCountdown}`,
        position: 'below',
        color: COLOR_COUNTDOWN,
        size: 'tiny',
      });
      if (buyCountdown >= 13) {
        buyCountdown = 0;
        buyComplete = false;
      }
    }

    // Sell countdown
    if (sellComplete && i >= 2 && close >= bars[i - 2].high) {
      sellCountdown++;
      labels.push({
        time: bars[i].time,
        value: bars[i].high,
        text: `+${sellCountdown}`,
        position: 'above',
        color: COLOR_COUNTDOWN,
        size: 'tiny',
      });
      if (sellCountdown >= 13) {
        sellCountdown = 0;
        sellComplete = false;
      }
    }
  }

  return labels;
}
