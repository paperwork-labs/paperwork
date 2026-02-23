import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/testing-library';
import { renderWithProviders } from '../../../test/render';
import StatCard from '../StatCard';

describe('StatCard', () => {
  it('renders label and value', () => {
    renderWithProviders(<StatCard label="Total" value="$10,000" />);
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('$10,000')).toBeInTheDocument();
  });

  it('renders sub when provided', () => {
    renderWithProviders(<StatCard label="P&L" value="+5%" sub="vs cost" />);
    expect(screen.getByText('vs cost')).toBeInTheDocument();
  });

  it('renders compact variant by default', () => {
    renderWithProviders(<StatCard label="X" value="1" />);
    expect(screen.getByText('X')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('handles numeric value', () => {
    renderWithProviders(<StatCard label="Count" value={42} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });
});
