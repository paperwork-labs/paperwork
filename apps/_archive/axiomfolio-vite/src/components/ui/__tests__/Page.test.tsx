import React from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { PageContainer } from '../Page';

describe('PageContainer', () => {
  it('applies the correct max-width class per variant', () => {
    const { rerender, container } = render(
      <PageContainer width="narrow" data-testid="pc">
        x
      </PageContainer>,
    );
    const el = () => container.querySelector('[data-testid="pc"]');
    expect(el()).toHaveClass('max-w-[640px]');

    rerender(
      <PageContainer width="default" data-testid="pc">
        x
      </PageContainer>,
    );
    expect(el()).toHaveClass('max-w-[960px]');

    rerender(
      <PageContainer width="wide" data-testid="pc">
        x
      </PageContainer>,
    );
    expect(el()).toHaveClass('max-w-[1200px]');

    rerender(
      <PageContainer width="full" data-testid="pc">
        x
      </PageContainer>,
    );
    expect(el()).toHaveClass('max-w-none');
    expect(el()).not.toHaveClass('max-w-[960px]');
  });

  it('merges className with cn() alongside width styles', () => {
    const { container } = render(
      <PageContainer width="default" className="mt-2 flex" data-testid="pc">
        x
      </PageContainer>,
    );
    const el = container.querySelector('[data-testid="pc"]');
    expect(el).toHaveClass('mt-2');
    expect(el).toHaveClass('flex');
    expect(el).toHaveClass('max-w-[960px]');
    expect(el).toHaveClass('mx-auto');
  });
});
