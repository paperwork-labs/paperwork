import React from 'react';
import { describe, it, expect } from 'vitest';
import { screen } from '@/test/testing-library';
import { renderWithProviders } from '../../../test/render';
import StageBar from '../StageBar';

describe('StageBar', () => {
  it('renders No data when total is 0', () => {
    renderWithProviders(<StageBar counts={{ '1A': 0, '2A': 0, '2B': 0, '2C': 0, '3A': 0, '4A': 0 }} total={0} />);
    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('renders stage badges with counts', () => {
    renderWithProviders(
      <StageBar counts={{ '1A': 1, '2A': 2, '2B': 0, '2C': 0, '3A': 0, '4A': 0 }} total={3} />
    );
    expect(screen.getByText(/1A: 1/)).toBeInTheDocument();
    expect(screen.getByText(/2A: 2/)).toBeInTheDocument();
  });

  it('renders proportional bar when total > 0', () => {
    renderWithProviders(
      <StageBar counts={{ '1A': 1, '2A': 1, '2B': 0, '2C': 0, '3A': 0, '4A': 0 }} total={2} />
    );
    expect(screen.getByText(/2A: 1 \(50%\)/)).toBeInTheDocument();
  });

  it('has accessible role and aria-label for stage distribution', () => {
    const { container } = renderWithProviders(
      <StageBar counts={{ '1A': 1, '2A': 2, '2B': 0, '2C': 0, '3A': 0, '4A': 0 }} total={3} />
    );
    const bar = container.querySelector('[role="img"][aria-label*="Stage distribution"]');
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute('aria-label');
    const label = bar?.getAttribute('aria-label') ?? '';
    expect(label).toMatch(/^Stage distribution:/);
    expect(label).toContain('1A: 1');
    expect(label).toContain('2A: 2');
  });
});
