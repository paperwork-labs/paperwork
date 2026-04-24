import React from 'react';
import { describe, it, expect } from 'vitest';
import { screen } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import SignalsHub from '../index';

describe('signals/index (SignalsHub)', () => {
  it('renders links to each signal surface', () => {
    renderWithProviders(<SignalsHub />);
    expect(screen.getByRole('link', { name: /candidates/i })).toHaveAttribute(
      'href',
      '/signals/candidates',
    );
    expect(screen.getByRole('link', { name: /regime/i })).toHaveAttribute(
      'href',
      '/signals/regime',
    );
    expect(screen.getByRole('link', { name: /stage scan/i })).toHaveAttribute(
      'href',
      '/signals/stage-scan',
    );
    expect(screen.getByRole('link', { name: /picks/i })).toHaveAttribute(
      'href',
      '/signals/picks',
    );
  });
});
