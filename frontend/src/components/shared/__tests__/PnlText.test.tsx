import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderWithProviders } from '../../../test/render';
import PnlText from '../PnlText';

describe('PnlText', () => {
  it('renders positive value with + in currency format', () => {
    renderWithProviders(<PnlText value={100} format="currency" />);
    expect(screen.getByText(/\+/)).toBeInTheDocument();
  });

  it('renders negative value in currency format', () => {
    renderWithProviders(<PnlText value={-50} format="currency" />);
    expect(screen.getByText(/-/)).toBeInTheDocument();
  });

  it('renders zero', () => {
    renderWithProviders(<PnlText value={0} format="currency" />);
    expect(screen.getByText('$0')).toBeInTheDocument();
  });

  it('renders percent format', () => {
    renderWithProviders(<PnlText value={2.5} format="percent" />);
    expect(screen.getByText(/\+2\.50%/)).toBeInTheDocument();
  });
});
