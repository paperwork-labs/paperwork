import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, screen, waitFor } from '@/test/testing-library';

import { renderWithProviders } from '@/test/render';
import PublicStatsStrip from '../PublicStatsStrip';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  default: { get },
}));

describe('PublicStatsStrip', () => {
  beforeEach(() => {
    get.mockResolvedValue({
      data: {
        portfolios_tracked: 3,
        charts_rendered_24h: 100,
        brokers_supported: 2,
      },
    });
  });

  afterEach(() => {
    cleanup();
    get.mockReset();
  });

  it('renders stat labels after load', async () => {
    renderWithProviders(<PublicStatsStrip />);
    await waitFor(() => {
      expect(screen.getByTestId('public-stats-strip')).toBeInTheDocument();
    });
    expect(screen.getByText('Portfolios tracked')).toBeInTheDocument();
  });

  it('respects prefers-reduced-motion: skips animating from zero when reduced', async () => {
    const mql = {
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (q: string) => ({ ...mql, media: q, onchange: null, dispatchEvent: vi.fn() }) as unknown as MediaQueryList,
    );

    renderWithProviders(<PublicStatsStrip />);
    await waitFor(() => {
      expect(screen.getByTestId('public-stats-strip')).toBeInTheDocument();
    });
    expect(screen.getByText('3')).toBeInTheDocument();

    vi.mocked(window.matchMedia).mockRestore();
  });
});
