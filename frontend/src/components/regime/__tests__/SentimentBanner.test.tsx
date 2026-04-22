import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as sentimentHook from '@/hooks/useSentimentComposite';
import SentimentBanner from '../SentimentBanner';
import { renderWithProviders } from '../../../test/render';

vi.mock('@/hooks/useSentimentComposite', () => ({
  useSentimentComposite: vi.fn(),
}));

const mockHook = vi.mocked(sentimentHook.useSentimentComposite);

function baseQuery(over: Partial<ReturnType<typeof sentimentHook.useSentimentComposite>>) {
  return {
    data: undefined,
    error: null,
    status: 'pending',
    isPending: true,
    isError: false,
    isSuccess: false,
    isRefetching: false,
    refetch: vi.fn().mockResolvedValue({}),
    ...over,
  } as ReturnType<typeof sentimentHook.useSentimentComposite>;
}

describe('SentimentBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading skeleton (one line)', () => {
    mockHook.mockReturnValue(
      baseQuery({ isPending: true, data: undefined, status: 'pending' }),
    );
    const { container } = renderWithProviders(<SentimentBanner />);
    expect(container.querySelector('[role="status"]')).toBeTruthy();
  });

  it('renders error with retry', async () => {
    const refetch = vi.fn().mockResolvedValue({});
    mockHook.mockReturnValue(
      baseQuery({
        isPending: false,
        isError: true,
        status: 'error',
        error: new Error('Network down'),
        data: undefined,
        refetch,
      }),
    );
    renderWithProviders(<SentimentBanner />);
    expect(screen.getByText('Sentiment unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network down')).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refetch).toHaveBeenCalled();
  });

  it('renders partial data without silent zeros (Regime and VIX; stubs show em dash)', () => {
    mockHook.mockReturnValue(
      baseQuery({
        isPending: false,
        isSuccess: true,
        status: 'success',
        data: {
          vix: 18.4,
          aaii: null,
          fear_greed: null,
          regime: { state: 'R3', score: 2.5 },
          asof: '2026-04-22T12:00:00+00:00',
        },
      }),
    );
    renderWithProviders(<SentimentBanner />);
    expect(screen.getByText(/R3 — Chop/)).toBeInTheDocument();
    expect(screen.getByText('18.4')).toBeInTheDocument();
    expect(screen.getByText('AAII')).toBeInTheDocument();
    expect(screen.getByText('F&G')).toBeInTheDocument();
  });

  it('renders full data when all fields present', () => {
    mockHook.mockReturnValue(
      baseQuery({
        isPending: false,
        isSuccess: true,
        status: 'success',
        data: {
          vix: 16.2,
          aaii: { bull: 0.4, bear: 0.35, net: 5 },
          fear_greed: { value: 52, label: 'Neutral' },
          regime: { state: 'R1', score: 1.25 },
          asof: '2026-04-22T12:00:00+00:00',
        },
      }),
    );
    renderWithProviders(<SentimentBanner />);
    expect(screen.getByText(/R1 — Bull/)).toBeInTheDocument();
    expect(screen.getByText('16.2')).toBeInTheDocument();
    expect(screen.getByText(/AAII \+5/)).toBeInTheDocument();
    expect(screen.getByText('52')).toBeInTheDocument();
    expect(screen.getByText(/Neutral/)).toBeInTheDocument();
  });
});
