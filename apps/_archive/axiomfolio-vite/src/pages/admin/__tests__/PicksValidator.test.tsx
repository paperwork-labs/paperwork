import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@/test/render';
import PicksValidator from '../PicksValidator';

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  default: {
    get,
    post,
    patch,
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('PicksValidator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockImplementation((url: string) => {
      if (url === '/admin/picks/queue/counts') {
        return Promise.resolve({ data: { DRAFT: 1, APPROVED: 0, PUBLISHED: 0, REJECTED: 0 } });
      }
      if (url.startsWith('/admin/picks/queue?state=DRAFT')) {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 9,
                ticker: 'NVDA',
                action: 'BUY',
                state: 'DRAFT',
                confidence: 88.5,
                thesis: 'Stage 2A',
                target_price: null,
                stop_loss: null,
                generator_name: 'test_gen',
                generator_version: 'v1',
                generated_at: new Date().toISOString(),
                published_at: null,
                state_transitioned_at: null,
                state_transitioned_by: null,
                source_email_parse_id: null,
              },
            ],
            total: 1,
            limit: 50,
            offset: 0,
          },
        });
      }
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    post.mockResolvedValue({ data: {} });
  });

  it('renders draft tab and runs approve mutation', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PicksValidator />);

    await waitFor(() => {
      expect(screen.getByText('NVDA')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/admin/picks/9/approve');
    });
  });
});
