import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderWithProviders } from '../../../test/render';
import StageBadge from '../StageBadge';

describe('StageBadge', () => {
  it('renders stage label', () => {
    renderWithProviders(<StageBadge stage="2A" />);
    expect(screen.getByText('2A')).toBeInTheDocument();
  });

  it('renders unknown stage', () => {
    renderWithProviders(<StageBadge stage="?" />);
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('accepts size prop', () => {
    renderWithProviders(<StageBadge stage="1" size="md" />);
    expect(screen.getByText('1')).toBeInTheDocument();
  });
});
