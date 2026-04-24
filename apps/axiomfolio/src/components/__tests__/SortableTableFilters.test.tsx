import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@/test/testing-library';
import { renderWithProviders } from '../../test/render';
import SortableTable, { type Column, type FilterGroup } from '../SortableTable';

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'UTC',
    tableDensity: 'comfortable',
  }),
}));

describe('SortableTable filters', () => {
  it('filters rows based on text rule', async () => {
    const columns: Column<any>[] = [
      { key: 'name', header: 'Name', accessor: (r) => r.name, sortable: true, sortType: 'string' },
      { key: 'sector', header: 'Sector', accessor: (r) => r.sector, sortable: true, sortType: 'string' },
    ];
    const data = [
      { name: 'AAPL', sector: 'Tech' },
      { name: 'JNJ', sector: 'Healthcare' },
    ];

    renderWithProviders(<SortableTable data={data} columns={columns} filtersEnabled />);

    fireEvent.click(screen.getByRole('button', { name: /add filter/i }));
    const inputs = screen.getAllByPlaceholderText('Value');
    fireEvent.change(inputs[0], { target: { value: 'AAPL' } });

    await waitFor(
      () => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
        expect(screen.queryByText('JNJ')).toBeNull();
      },
      { timeout: 400 }
    );
  });

  it('applies filter presets', () => {
    const columns: Column<any>[] = [
      { key: 'price', header: 'Price', accessor: (r) => r.price, sortable: true, sortType: 'number' },
      { key: 'sma_5', header: 'SMA 5', accessor: (r) => r.sma_5, sortable: true, sortType: 'number' },
    ];
    const data = [
      { price: 10, sma_5: 8 },
      { price: 5, sma_5: 6 },
    ];
    const filterPresets: Array<{ label: string; filters: FilterGroup }> = [
      {
        label: 'Price > SMA5',
        filters: {
          conjunction: 'AND',
          rules: [
            {
              id: 'preset_price_gt_sma',
              columnKey: 'price',
              operator: 'gt',
              valueSource: 'column',
              valueColumnKey: 'sma_5',
            },
          ],
        },
      },
    ];

    renderWithProviders(
      <SortableTable data={data} columns={columns} filtersEnabled filterPresets={filterPresets} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /price > sma5/i }));
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.queryByText('5')).toBeNull();
  });
});

