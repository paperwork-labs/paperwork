import * as React from 'react';
import { describe, expect, it } from 'vitest';
import { act, render } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';

import {
  __test,
  useHoldingChartUrlState,
  type OverlayId,
} from '../useHoldingChartUrlState';

describe('useHoldingChartUrlState (pure encoders)', () => {
  it('parsePeriod returns fallback for unknown values', () => {
    expect(__test.parsePeriod('1y', '3mo')).toBe('1y');
    expect(__test.parsePeriod('not-a-period', '3mo')).toBe('3mo');
    expect(__test.parsePeriod(null, '3mo')).toBe('3mo');
    expect(__test.parsePeriod('', '6mo')).toBe('6mo');
  });

  it('parseOverlays drops unknowns + dedupes + canonicalizes order', () => {
    expect(__test.parseOverlays('sma200,bb,sma50,sma50,bogus')).toEqual([
      'sma50',
      'sma200',
      'bollinger',
    ]);
    expect(__test.parseOverlays('')).toEqual([]);
    expect(__test.parseOverlays(null)).toEqual([]);
  });

  it('parseStageBands accepts only "1" / "true"', () => {
    expect(__test.parseStageBands('1')).toBe(true);
    expect(__test.parseStageBands('true')).toBe(true);
    expect(__test.parseStageBands('0')).toBe(false);
    expect(__test.parseStageBands(null)).toBe(false);
  });

  it('parseBenchmark uppercases and validates symbol-shape', () => {
    expect(__test.parseBenchmark('spy')).toBe('SPY');
    expect(__test.parseBenchmark('BRK.B')).toBe('BRK.B');
    expect(__test.parseBenchmark('')).toBeNull();
    expect(__test.parseBenchmark('not a symbol')).toBeNull();
    expect(__test.parseBenchmark('TOOLONGSYMBOLXX')).toBeNull();
  });

  it('encodeOverlays produces canonical-order wire tokens', () => {
    expect(__test.encodeOverlays(['bollinger', 'sma50'])).toBe('sma50,bb');
    expect(__test.encodeOverlays(['sma200', 'sma100', 'sma50'])).toBe(
      'sma50,sma100,sma200',
    );
    expect(__test.encodeOverlays([])).toBeNull();
  });

  it('round-trips overlays via the wire shorthand', () => {
    const overlays: OverlayId[] = ['sma50', 'bollinger', 'ema21'];
    const encoded = __test.encodeOverlays(overlays);
    expect(encoded).toBeTruthy();
    expect(__test.parseOverlays(encoded as string)).toEqual([
      'sma50',
      'ema21',
      'bollinger',
    ]);
  });
});

interface ProbeProps {
  defaults?: Parameters<typeof useHoldingChartUrlState>[0];
  onState?: (s: ReturnType<typeof useHoldingChartUrlState>) => void;
  apply?: (s: ReturnType<typeof useHoldingChartUrlState>) => void;
}

function Probe({ defaults, onState, apply }: ProbeProps) {
  const state = useHoldingChartUrlState(defaults);
  const location = useLocation();
  React.useEffect(() => {
    onState?.(state);
  });
  const appliedRef = React.useRef(false);
  React.useEffect(() => {
    if (!apply || appliedRef.current) return;
    appliedRef.current = true;
    apply(state);
  }, [apply, state]);
  return <div data-testid="search">{location.search}</div>;
}

describe('useHoldingChartUrlState (hook)', () => {
  it('reads URL params and applies sane defaults', () => {
    let captured: ReturnType<typeof useHoldingChartUrlState> | null = null;
    render(
      <MemoryRouter
        initialEntries={[
          '/holding/AAPL?period=3mo&overlays=sma50,bb&stageBands=1&benchmark=spy',
        ]}
      >
        <Probe onState={(s) => (captured = s)} />
      </MemoryRouter>,
    );
    expect(captured).toBeTruthy();
    expect(captured!.period).toBe('3mo');
    expect(captured!.overlays).toEqual(['sma50', 'bollinger']);
    expect(captured!.stageBands).toBe(true);
    expect(captured!.benchmark).toBe('SPY');
  });

  it('falls back to defaults when params are missing', () => {
    let captured: ReturnType<typeof useHoldingChartUrlState> | null = null;
    render(
      <MemoryRouter initialEntries={['/holding/AAPL']}>
        <Probe
          defaults={{
            defaultPeriod: '6mo',
            defaultOverlays: ['sma200'],
            defaultStageBands: true,
            defaultBenchmark: 'SPY',
          }}
          onState={(s) => (captured = s)}
        />
      </MemoryRouter>,
    );
    expect(captured!.period).toBe('6mo');
    expect(captured!.overlays).toEqual(['sma200']);
    expect(captured!.stageBands).toBe(true);
    expect(captured!.benchmark).toBe('SPY');
  });

  it('drops unknown overlay tokens silently (validation)', () => {
    let captured: ReturnType<typeof useHoldingChartUrlState> | null = null;
    render(
      <MemoryRouter
        initialEntries={['/holding/AAPL?overlays=bb,does-not-exist,sma50']}
      >
        <Probe onState={(s) => (captured = s)} />
      </MemoryRouter>,
    );
    expect(captured!.overlays).toEqual(['sma50', 'bollinger']);
  });

  it('round-trips a setOverlays update through the URL', async () => {
    let captured: ReturnType<typeof useHoldingChartUrlState> | null = null;
    let pushed = false;
    const { getByTestId } = render(
      <MemoryRouter initialEntries={['/holding/AAPL']}>
        <Probe
          onState={(s) => (captured = s)}
          apply={(s) => {
            if (pushed) return;
            pushed = true;
            s.setOverlays(['bollinger', 'sma50']);
          }}
        />
      </MemoryRouter>,
    );
    await act(async () => {
      // Allow the effect-driven setOverlays to flush.
      await Promise.resolve();
    });
    // URL got the canonical-order wire format.
    expect(getByTestId('search').textContent).toContain('overlays=sma50%2Cbb');
    expect(captured!.overlays).toEqual(['sma50', 'bollinger']);
  });

  it('omits keys when they equal the absent / default value', async () => {
    const { getByTestId } = render(
      <MemoryRouter initialEntries={['/holding/AAPL?stageBands=1']}>
        <Probe
          apply={(s) => {
            s.setAll({ stageBands: false, overlays: [] });
          }}
        />
      </MemoryRouter>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    const search = getByTestId('search').textContent ?? '';
    expect(search).not.toContain('stageBands');
    expect(search).not.toContain('overlays');
  });
});
