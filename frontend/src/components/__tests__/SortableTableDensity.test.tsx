import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderWithProviders } from '../../test/render';
import SortableTable, { type Column } from '../SortableTable';

// Keep most Chakra exports real, but replace table primitives so we can assert `size`.
vi.mock('@chakra-ui/react', async () => {
  const actual: any = await vi.importActual('@chakra-ui/react');
  return {
    ...actual,
    TableScrollArea: ({ children }: any) => <div>{children}</div>,
    TableRoot: ({ children, size, ...rest }: any) => (
      <table data-testid="table-root" data-size={size} {...rest}>
        {children}
      </table>
    ),
    TableHeader: ({ children }: any) => <thead>{children}</thead>,
    TableBody: ({ children }: any) => <tbody>{children}</tbody>,
    // Drop Chakra-style props like `textAlign`/`borderColor` to avoid React warnings in this test.
    TableRow: ({ children }: any) => <tr>{children}</tr>,
    TableColumnHeader: ({ children, onClick }: any) => <th onClick={onClick}>{children}</th>,
    TableCell: ({ children }: any) => <td>{children}</td>,
  };
});

vi.mock('../../hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({
    currency: 'USD',
    timezone: 'UTC',
    tableDensity: 'compact',
  }),
}));

describe('SortableTable table density default', () => {
  it('defaults to size="sm" when user table_density is compact and size prop is not set', () => {
    const columns: Column<any>[] = [
      { key: 'name', header: 'Name', accessor: (r) => r.name },
    ];
    const { getByTestId } = renderWithProviders(<SortableTable data={[{ name: 'A' }]} columns={columns} />);
    expect(getByTestId('table-root')).toHaveAttribute('data-size', 'sm');
  });

  it('respects explicit size prop even when user table_density is compact', () => {
    const columns: Column<any>[] = [
      { key: 'name', header: 'Name', accessor: (r) => r.name },
    ];
    const { getAllByTestId } = renderWithProviders(<SortableTable data={[{ name: 'A' }]} columns={columns} size="lg" />);
    const tables = getAllByTestId('table-root');
    expect(tables.some((t: Element) => t.getAttribute('data-size') === 'lg')).toBe(true);
  });
});


