import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderWithProviders } from '../../../test/render';
import StageBar from '../StageBar';

describe('StageBar', () => {
  it('renders No data when total is 0', () => {
    renderWithProviders(<StageBar counts={{ '1': 0, '2A': 0, '2B': 0, '2C': 0, '3': 0, '4': 0 }} total={0} />);
    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('renders stage badges with counts', () => {
    renderWithProviders(
      <StageBar counts={{ '1': 1, '2A': 2, '2B': 0, '2C': 0, '3': 0, '4': 0 }} total={3} />
    );
    expect(screen.getByText(/1: 1/)).toBeInTheDocument();
    expect(screen.getByText(/2A: 2/)).toBeInTheDocument();
  });

  it('renders proportional bar when total > 0', () => {
    renderWithProviders(
      <StageBar counts={{ '1': 1, '2A': 1, '2B': 0, '2C': 0, '3': 0, '4': 0 }} total={2} />
    );
    expect(screen.getByText(/2A: 1 \(50%\)/)).toBeInTheDocument();
  });

  it('has accessible role and aria-label for stage distribution', () => {
    const { container } = renderWithProviders(
      <StageBar counts={{ '1': 1, '2A': 2, '2B': 0, '2C': 0, '3': 0, '4': 0 }} total={3} />
    );
    const bar = container.querySelector('[role="img"][aria-label*="Stage distribution"]');
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute('aria-label');
    expect(bar?.getAttribute('aria-label')).toMatch(/Stage distribution:.*1: 1.*2A: 2/);
  });
});
