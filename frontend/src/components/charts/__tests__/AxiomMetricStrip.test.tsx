import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AxiomMetricStrip } from '../AxiomMetricStrip';

describe('AxiomMetricStrip', () => {
  it('renders a skeleton when loading', () => {
    render(<AxiomMetricStrip values={{}} loading />);
    expect(screen.getByTestId('metric-strip-skeleton')).toBeInTheDocument();
    expect(screen.queryByTestId('axiom-metric-strip')).toBeNull();
  });

  it('renders all six metric cards with sensible labels', () => {
    render(
      <AxiomMetricStrip
        values={{
          stageLabel: '2A',
          rsi: 62.5,
          atrPct: 2.1,
          macd: 0.45,
          adx: 28,
          rsMansfield: 1.4,
        }}
      />,
    );
    expect(screen.getByTestId('axiom-metric-strip')).toBeInTheDocument();
    expect(screen.getByText('Stage')).toBeInTheDocument();
    expect(screen.getByText('RSI')).toBeInTheDocument();
    expect(screen.getByText('ATR%')).toBeInTheDocument();
    expect(screen.getByText('MACD')).toBeInTheDocument();
    expect(screen.getByText('ADX')).toBeInTheDocument();
    expect(screen.getByText('RS Mansfield')).toBeInTheDocument();
  });

  it('renders em-dash for null / non-finite metric values', () => {
    render(
      <AxiomMetricStrip
        values={{
          stageLabel: null,
          rsi: null,
          atrPct: Number.NaN,
          macd: undefined,
          adx: null,
          rsMansfield: null,
        }}
      />,
    );
    // 6 em-dashes: one per missing metric. Use getAllByText to avoid
    // brittleness if more cards land in the future.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(6);
  });

  it('signs the RS Mansfield value with explicit + when positive', () => {
    render(
      <AxiomMetricStrip
        values={{ rsMansfield: 2.34 }}
      />,
    );
    expect(screen.getByLabelText(/RS Mansfield \+2\.34/)).toBeInTheDocument();
  });

  it('exposes a group role with an accessible label', () => {
    render(<AxiomMetricStrip values={{ rsi: 50 }} />);
    expect(
      screen.getByRole('group', { name: /key indicator metrics/i }),
    ).toBeInTheDocument();
  });

  it('makes each card tabbable so keyboard users can read tooltips', () => {
    const { container } = render(
      <AxiomMetricStrip values={{ rsi: 50, stageLabel: '2A' }} />,
    );
    const tabbables = container.querySelectorAll('[tabindex="0"]');
    expect(tabbables.length).toBe(6);
  });
});
