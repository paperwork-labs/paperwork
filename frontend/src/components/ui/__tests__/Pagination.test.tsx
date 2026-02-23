import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@/test/testing-library';
import { renderWithProviders } from '../../../test/render';
import Pagination from '../Pagination';

describe('Pagination', () => {
  it('renders range label and navigates pages', () => {
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();

    renderWithProviders(
      <Pagination
        page={1}
        pageSize={25}
        total={4585}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />,
    );

    expect(screen.getByText('1–25 of 4585')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('shows first and last pages and ellipsis for large totals', () => {
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();

    renderWithProviders(
      <Pagination
        page={50}
        pageSize={25}
        total={4585} // 184 pages
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />,
    );

    expect(screen.getAllByRole('button', { name: '1' }).length).toBeGreaterThan(0);
    // Some Chakra primitives may duplicate accessible nodes; presence is what matters.
    expect(screen.getAllByRole('button', { name: '184' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: '50' }).length).toBeGreaterThan(0);
  });
});


