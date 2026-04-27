import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { FirstRunHero } from '../FirstRunHero';
import { renderWithProviders } from '@/test/render';

describe('FirstRunHero', () => {
  it('calls onEngage and scrolls to grid anchor', async () => {
    const user = userEvent.setup();
    const onEngage = vi.fn();
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    const grid = document.createElement('div');
    grid.id = 'broker-picker-grid';
    document.body.appendChild(grid);

    try {
      renderWithProviders(<FirstRunHero onEngage={onEngage} />);
      await user.click(screen.getByRole('button', { name: /choose a broker/i }));
      expect(onEngage).toHaveBeenCalled();
      expect(scrollIntoView).toHaveBeenCalled();
    } finally {
      grid.remove();
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
  });
});
