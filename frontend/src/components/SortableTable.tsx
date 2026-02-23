import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
  Box,
  Icon,
  HStack,
  Text,
  Button,
  NativeSelectRoot,
  NativeSelectField,
  NativeSelectIndicator,
  Input,
} from '@chakra-ui/react';
import { FiChevronUp, FiChevronDown, FiMinus, FiPlus, FiX } from 'react-icons/fi';
import EmptyState from './ui/EmptyState';
import { useDebounce } from '../hooks/useDebounce';
import { useUserPreferences } from '../hooks/useUserPreferences';

const DEBOUNCE_MS = 300;

function DebouncedFilterInput({
  value,
  onChange,
  type = 'text',
  placeholder,
  size,
  w,
}: {
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'number' | 'date';
  placeholder?: string;
  size?: 'sm' | 'md' | 'lg';
  w?: string;
}) {
  const [localValue, setLocalValue] = useState(value ?? '');
  const debounced = useDebounce(localValue, DEBOUNCE_MS);
  const lastEmittedRef = useRef<string>(value ?? '');
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (value !== lastEmittedRef.current) setLocalValue(value ?? '');
  }, [value]);

  useEffect(() => {
    if (debounced !== lastEmittedRef.current) {
      onChangeRef.current(debounced);
      lastEmittedRef.current = debounced;
    }
  }, [debounced]);

  return (
    <Input
      size={size}
      w={w}
      type={type}
      value={localValue}
      onChange={(e) => setLocalValue(e.target.value)}
      placeholder={placeholder}
    />
  );
}

export type FilterType = 'text' | 'number' | 'select' | 'date';
export type FilterOperator =
  | 'contains'
  | 'equals'
  | 'starts_with'
  | 'ends_with'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'on'
  | 'before'
  | 'after';

export type FilterRule = {
  id: string;
  columnKey: string;
  operator: FilterOperator;
  valueSource?: 'literal' | 'column';
  valueColumnKey?: string;
  value?: string;
  valueTo?: string;
};

export type FilterGroup = {
  conjunction: 'AND' | 'OR';
  rules: FilterRule[];
};

export interface Column<T = any> {
  key: string;
  header: string;
  accessor: (item: T) => any;
  sortable?: boolean;
  sortType?: 'string' | 'number' | 'date';
  render?: (value: any, item: T) => React.ReactNode;
  width?: string;
  isNumeric?: boolean;
  filterType?: FilterType;
  filterOptions?: Array<{ label: string; value: string }>;
  filterable?: boolean;
  /** When true the column is available for sorting/filtering but hidden from the table by default. */
  hidden?: boolean;
}

interface SortableTableProps<T = any> {
  data: T[];
  columns: Column<T>[];
  defaultSortBy?: string;
  defaultSortOrder?: 'asc' | 'desc';
  size?: 'sm' | 'md' | 'lg';
  variant?: 'simple' | 'striped' | 'unstyled';
  showHeader?: boolean;
  emptyMessage?: string;
  maxHeight?: string;
  filtersEnabled?: boolean;
  filterPresets?: Array<{ label: string; filters: FilterGroup }>;
  initialFilters?: FilterGroup;
  initialFiltersOpen?: boolean;
  collapseAfterPresetLabels?: string[];
  /** Optional row click handler; receives the row data. */
  onRowClick?: (row: T) => void;
}

function SortableTable<T = any>({
  data,
  columns,
  defaultSortBy,
  defaultSortOrder = 'desc',
  size: sizeProp,
  variant = 'simple',
  showHeader = true,
  emptyMessage = 'No data available',
  maxHeight,
  filtersEnabled = false,
  filterPresets = [],
  initialFilters,
  initialFiltersOpen = true,
  collapseAfterPresetLabels = [],
  onRowClick,
}: SortableTableProps<T>) {
  const { tableDensity } = useUserPreferences();
  const size: 'sm' | 'md' | 'lg' = sizeProp ?? (tableDensity === 'compact' ? 'sm' : 'md');
  const [sortBy, setSortBy] = useState<string>(defaultSortBy || columns[0]?.key || '');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>(defaultSortOrder);
  const [filters, setFilters] = useState<FilterGroup>({
    conjunction: initialFilters?.conjunction || 'AND',
    rules: initialFilters?.rules || [],
  });
  const [filtersOpen, setFiltersOpen] = useState(initialFiltersOpen);

  const visibleColumns = useMemo(() => columns.filter((c) => !c.hidden), [columns]);

  const borderColor = 'border.subtle';
  const hoverBg = 'bg.panel';

  const handleSort = (columnKey: string) => {
    const column = columns.find(col => col.key === columnKey);
    if (!column?.sortable) return;

    if (sortBy === columnKey) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(columnKey);
      setSortOrder('desc');
    }
  };

  const getSortIcon = (columnKey: string) => {
    const column = columns.find(col => col.key === columnKey);
    if (!column?.sortable) return <Icon as={FiMinus} color="transparent" />;

    if (sortBy !== columnKey) {
      return <Icon as={FiMinus} color="fg.subtle" />;
    }

    return sortOrder === 'asc'
      ? <Icon as={FiChevronUp} color="brand.500" />
      : <Icon as={FiChevronDown} color="brand.500" />;
  };

  // Chakra v3 table variants differ from v2. Normalize our legacy variants.
  const tableVariant: 'line' | 'outline' | undefined = variant === 'unstyled' ? undefined : 'line';

  const filterableColumns = useMemo(
    () => columns.filter((col) => col.filterable !== false),
    [columns],
  );

  const columnMeta = useMemo(() => {
    const meta = new Map<string, { type: FilterType; options?: Array<{ label: string; value: string }> }>();
    columns.forEach((col) => {
      const inferred: FilterType =
        col.filterType ||
        (col.sortType === 'number' ? 'number' : col.sortType === 'date' ? 'date' : 'text');
      meta.set(col.key, { type: inferred, options: col.filterOptions });
    });
    return meta;
  }, [columns]);

  const filterOptionsByKey = useMemo(() => {
    const out = new Map<string, Array<{ label: string; value: string }>>();
    columns.forEach((col) => {
      const meta = columnMeta.get(col.key);
      if (meta?.type !== 'select') return;
      if (meta?.options && meta.options.length) {
        out.set(col.key, meta.options);
        return;
      }
      const values = new Set<string>();
      data.forEach((row) => {
        const v = col.accessor(row);
        if (v == null) return;
        values.add(String(v));
      });
      const options = Array.from(values)
        .slice(0, 50)
        .map((v) => ({ label: v, value: v }));
      out.set(col.key, options);
    });
    return out;
  }, [columns, columnMeta, data]);

  const operatorOptions = (type: FilterType): Array<{ label: string; value: FilterOperator }> => {
    if (type === 'number') {
      return [
        { label: '>', value: 'gt' },
        { label: '≥', value: 'gte' },
        { label: '<', value: 'lt' },
        { label: '≤', value: 'lte' },
        { label: '=', value: 'equals' },
        { label: 'Between', value: 'between' },
      ];
    }
    if (type === 'date') {
      return [
        { label: 'On', value: 'on' },
        { label: 'Before', value: 'before' },
        { label: 'After', value: 'after' },
        { label: 'Between', value: 'between' },
      ];
    }
    if (type === 'select') {
      return [{ label: 'Is', value: 'equals' }];
    }
    return [
      { label: 'Contains', value: 'contains' },
      { label: 'Equals', value: 'equals' },
      { label: 'Starts with', value: 'starts_with' },
      { label: 'Ends with', value: 'ends_with' },
    ];
  };

  const addFilterRule = () => {
    const fallbackKey = filterableColumns[0]?.key || columns[0]?.key || '';
    if (!fallbackKey) return;
    const meta = columnMeta.get(fallbackKey);
    const ops = operatorOptions(meta?.type || 'text');
    setFilters((prev) => ({
      ...prev,
      rules: [
        ...prev.rules,
        {
          id: `f_${Date.now()}_${Math.random().toString(16).slice(2)}`,
          columnKey: fallbackKey,
          operator: ops[0]?.value || 'contains',
          valueSource: 'literal',
          value: '',
        },
      ],
    }));
  };

  const updateRule = (id: string, next: Partial<FilterRule>) => {
    setFilters((prev) => ({
      ...prev,
      rules: prev.rules.map((r) => (r.id === id ? { ...r, ...next } : r)),
    }));
  };

  const removeRule = (id: string) => {
    setFilters((prev) => ({
      ...prev,
      rules: prev.rules.filter((r) => r.id !== id),
    }));
  };

  const clearFilters = () => {
    setFilters((prev) => ({ ...prev, rules: [] }));
  };

  const normalizeDateKey = (value: any): string | null => {
    if (!value) return null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  };

  const comparableColumns = (type: FilterType, excludeKey?: string) =>
    filterableColumns.filter((col) => {
      if (excludeKey && col.key === excludeKey) return false;
      const meta = columnMeta.get(col.key);
      const t = meta?.type || 'text';
      return t === type;
    });

  const ruleIsActive = (rule: FilterRule) => {
    if (rule.valueSource === 'column') {
      return Boolean(rule.valueColumnKey);
    }
    if (rule.operator === 'between') {
      return Boolean(rule.value) && Boolean(rule.valueTo);
    }
    return rule.value != null && String(rule.value).trim() !== '';
  };

  const ruleSummary = (rule: FilterRule) => {
    if (!ruleIsActive(rule)) return null;
    const col = columns.find((c) => c.key === rule.columnKey);
    const label = col?.header || rule.columnKey;
    const opLabel: Record<FilterOperator, string> = {
      contains: 'contains',
      equals: '=',
      starts_with: 'starts with',
      ends_with: 'ends with',
      gt: '>',
      gte: '≥',
      lt: '<',
      lte: '≤',
      between: 'between',
      on: 'on',
      before: 'before',
      after: 'after',
    };
    const operator = opLabel[rule.operator] || rule.operator;
    const valueLabel = () => {
      if (rule.valueSource === 'column') {
        const other = columns.find((c) => c.key === rule.valueColumnKey);
        return other?.header || rule.valueColumnKey || '';
      }
      return String(rule.value ?? '').trim();
    };
    if (rule.operator === 'between') {
      return `${label} ${operator} ${rule.value ?? ''} and ${rule.valueTo ?? ''}`.trim();
    }
    return `${label} ${operator} ${valueLabel()}`.trim();
  };

  const filterSummary = useMemo(() => {
    if (!filtersEnabled || filters.rules.length === 0) return '';
    const parts = filters.rules.map(ruleSummary).filter(Boolean) as string[];
    if (!parts.length) return '';
    const joiner = filters.conjunction === 'OR' ? ' OR ' : '; ';
    let summary = parts.join(joiner);
    if (summary.length > 160) {
      summary = `${summary.slice(0, 160)}…`;
    }
    return summary;
  }, [filtersEnabled, filters, columns]);

  const filteredData = useMemo(() => {
    if (!filtersEnabled || filters.rules.length === 0) return data;

    const applyRule = (row: T, rule: FilterRule) => {
      if (!ruleIsActive(rule)) return true;
      const col = columns.find((c) => c.key === rule.columnKey);
      if (!col) return true;
      const meta = columnMeta.get(rule.columnKey);
      const type = meta?.type || 'text';
      const raw = col.accessor(row);
      if (raw == null) return false;

      const resolveCompareValue = () => {
        if (rule.valueSource !== 'column') return rule.value;
        const other = columns.find((c) => c.key === rule.valueColumnKey);
        if (!other) return undefined;
        return other.accessor(row);
      };

      if (type === 'number') {
        const num = Number(raw);
        const compareValue = resolveCompareValue();
        const val = Number(compareValue);
        const valTo = Number(rule.valueTo);
        if (!Number.isFinite(num) || !Number.isFinite(val)) return false;
        switch (rule.operator) {
          case 'gt':
            return num > val;
          case 'gte':
            return num >= val;
          case 'lt':
            return num < val;
          case 'lte':
            return num <= val;
          case 'between':
            return Number.isFinite(valTo) ? num >= Math.min(val, valTo) && num <= Math.max(val, valTo) : true;
          case 'equals':
          default:
            return num === val;
        }
      }

      if (type === 'date') {
        const key = normalizeDateKey(raw);
        const compareValue = resolveCompareValue();
        const valKey = normalizeDateKey(compareValue);
        const valToKey = normalizeDateKey(rule.valueTo);
        if (!key || !valKey) return false;
        switch (rule.operator) {
          case 'before':
            return key < valKey;
          case 'after':
            return key > valKey;
          case 'between':
            if (!valToKey) return true;
            return key >= (valKey < valToKey ? valKey : valToKey) && key <= (valKey > valToKey ? valKey : valToKey);
          case 'on':
          default:
            return key === valKey;
        }
      }

      const value = String(raw).toLowerCase();
      const compareValue = resolveCompareValue();
      const needle = String(compareValue || '').toLowerCase();
      switch (rule.operator) {
        case 'equals':
          return value === needle;
        case 'starts_with':
          return value.startsWith(needle);
        case 'ends_with':
          return value.endsWith(needle);
        case 'contains':
        default:
          return value.includes(needle);
      }
    };

    const ruleResults = (row: T) => filters.rules.map((rule) => applyRule(row, rule));
    if (filters.conjunction === 'OR') {
      return data.filter((row) => ruleResults(row).some(Boolean));
    }
    return data.filter((row) => ruleResults(row).every(Boolean));
  }, [data, filters, filtersEnabled, columns, columnMeta]);

  const sortedData = useMemo(() => {
    if (!sortBy || !filteredData.length) return filteredData;

    const column = columns.find(col => col.key === sortBy);
    if (!column) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aValue = column.accessor(a);
      const bValue = column.accessor(b);

      // Handle null/undefined values
      if (aValue == null && bValue == null) return 0;
      if (aValue == null) return 1;
      if (bValue == null) return -1;

      let comparison = 0;

      switch (column.sortType) {
        case 'number':
          comparison = Number(aValue) - Number(bValue);
          break;
        case 'date':
          comparison = new Date(aValue).getTime() - new Date(bValue).getTime();
          break;
        case 'string':
        default:
          comparison = String(aValue).localeCompare(String(bValue));
          break;
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [filteredData, sortBy, sortOrder, columns]);

  if (!data.length) {
    return <EmptyState title={emptyMessage} />;
  }

  return (
    <Box w="full">
      {filtersEnabled && (
        <Box px={3} py={2} borderBottomWidth="1px" borderColor={borderColor} data-testid="table-filters">
          <HStack justify="space-between" flexWrap="wrap" gap={2}>
            <HStack gap={2} flexWrap="wrap">
              <Text fontSize="xs" color="fg.muted">Filters</Text>
              <Button size="xs" variant="ghost" onClick={() => setFiltersOpen((v) => !v)}>
                <HStack gap={1}>
                  <Text>{filtersOpen ? 'Hide' : 'Show'}</Text>
                </HStack>
              </Button>
              {filters.rules.length > 0 && (
                <Button size="xs" variant="ghost" onClick={clearFilters}>
                  Clear
                </Button>
              )}
            </HStack>
            <Text fontSize="xs" color="fg.muted">
              {sortedData.length} of {data.length}
            </Text>
          </HStack>

          {!filtersOpen && filterSummary && (
            <Text mt={1} fontSize="xs" color="fg.muted">
              Active: {filterSummary}
            </Text>
          )}

          {filtersOpen && (
            <Box mt={2}>
              <HStack gap={2} flexWrap="wrap">
                <NativeSelectRoot size="sm" w="auto">
                  <NativeSelectField
                    value={filters.conjunction}
                    onChange={(e) => setFilters((prev) => ({ ...prev, conjunction: e.target.value as 'AND' | 'OR' }))}
                  >
                    <option value="AND">Match all</option>
                    <option value="OR">Match any</option>
                  </NativeSelectField>
                  <NativeSelectIndicator />
                </NativeSelectRoot>
                <Button size="xs" variant="outline" onClick={addFilterRule}>
                  <HStack gap={1}>
                    <Icon as={FiPlus} />
                    <Text>Add filter</Text>
                  </HStack>
                </Button>
                {filterPresets.length > 0 && (
                  <HStack gap={1} flexWrap="wrap">
                    {filterPresets.map((preset) => (
                      <Button
                        key={preset.label}
                        size="xs"
                        variant="ghost"
                        onClick={() => {
                          setFilters(preset.filters);
                          setFiltersOpen(!collapseAfterPresetLabels.includes(preset.label));
                        }}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </HStack>
                )}
              </HStack>

              {filters.rules.length > 0 && (
                <Box mt={2} display="flex" flexDirection="column" gap={2}>
                  {filters.rules.map((rule) => {
                    const meta = columnMeta.get(rule.columnKey);
                    const type = meta?.type || 'text';
                    const ops = operatorOptions(type);
                    const options = filterOptionsByKey.get(rule.columnKey) || [];
                    const compareCols = comparableColumns(type, rule.columnKey);
                    return (
                      <HStack key={rule.id} gap={2} flexWrap="wrap">
                        <NativeSelectRoot size="sm" w="auto">
                          <NativeSelectField
                            value={rule.columnKey}
                            onChange={(e) => {
                              const nextKey = e.target.value;
                              const nextMeta = columnMeta.get(nextKey);
                              const nextOps = operatorOptions(nextMeta?.type || 'text');
                              updateRule(rule.id, {
                                columnKey: nextKey,
                                operator: nextOps[0]?.value || 'contains',
                                valueSource: 'literal',
                                valueColumnKey: undefined,
                                value: '',
                                valueTo: '',
                              });
                            }}
                          >
                            {filterableColumns.map((col) => (
                              <option key={col.key} value={col.key}>
                                {col.header}
                              </option>
                            ))}
                          </NativeSelectField>
                          <NativeSelectIndicator />
                        </NativeSelectRoot>

                        <NativeSelectRoot size="sm" w="auto">
                          <NativeSelectField
                            value={rule.operator}
                            onChange={(e) => updateRule(rule.id, { operator: e.target.value as FilterOperator })}
                          >
                            {ops.map((op) => (
                              <option key={op.value} value={op.value}>
                                {op.label}
                              </option>
                            ))}
                          </NativeSelectField>
                          <NativeSelectIndicator />
                        </NativeSelectRoot>

                        {compareCols.length > 0 && (
                          <NativeSelectRoot size="sm" w="auto">
                            <NativeSelectField
                              value={rule.valueSource || 'literal'}
                              onChange={(e) =>
                                updateRule(rule.id, {
                                  valueSource: e.target.value as 'literal' | 'column',
                                  value: '',
                                  valueTo: '',
                                  valueColumnKey: undefined,
                                })
                              }
                            >
                              <option value="literal">Value</option>
                              <option value="column">Column</option>
                            </NativeSelectField>
                            <NativeSelectIndicator />
                          </NativeSelectRoot>
                        )}

                        {rule.valueSource === 'column' ? (
                          <NativeSelectRoot size="sm" w="auto">
                            <NativeSelectField
                              value={rule.valueColumnKey || ''}
                              onChange={(e) => updateRule(rule.id, { valueColumnKey: e.target.value })}
                            >
                              <option value="">Select column…</option>
                              {compareCols.map((col) => (
                                <option key={col.key} value={col.key}>
                                  {col.header}
                                </option>
                              ))}
                            </NativeSelectField>
                            <NativeSelectIndicator />
                          </NativeSelectRoot>
                        ) : type === 'select' ? (
                          <NativeSelectRoot size="sm" w="auto">
                            <NativeSelectField
                              value={rule.value || ''}
                              onChange={(e) => updateRule(rule.id, { value: e.target.value })}
                            >
                              <option value="">Select…</option>
                              {options.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </NativeSelectField>
                            <NativeSelectIndicator />
                          </NativeSelectRoot>
                        ) : (
                          <DebouncedFilterInput
                            value={rule.value || ''}
                            onChange={(v) => updateRule(rule.id, { value: v })}
                            type={type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'}
                            placeholder="Value"
                            size="sm"
                            w="120px"
                          />
                        )}

                        {rule.operator === 'between' && rule.valueSource !== 'column' && (
                          <DebouncedFilterInput
                            value={rule.valueTo || ''}
                            onChange={(v) => updateRule(rule.id, { valueTo: v })}
                            type={type === 'number' ? 'number' : type === 'date' ? 'date' : 'text'}
                            placeholder="And"
                            size="sm"
                            w="120px"
                          />
                        )}

                        <Button size="xs" variant="ghost" onClick={() => removeRule(rule.id)}>
                          <Icon as={FiX} />
                        </Button>
                      </HStack>
                    );
                  })}
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}

      {sortedData.length === 0 ? (
        <EmptyState title="No results match filters" />
      ) : (
        <Box overflowX="auto" w="full">
        <TableScrollArea
          w="full"
          maxHeight={maxHeight}
          overflowY={maxHeight ? 'auto' : 'visible'}
          overflowX="auto"
        >
          <TableRoot w="full" variant={tableVariant} size={size}>
            {showHeader && (
              <TableHeader>
                <TableRow>
                  {visibleColumns.map((column) => (
                    <TableColumnHeader
                      key={column.key}
                      onClick={() => column.sortable && handleSort(column.key)}
                      cursor={column.sortable ? 'pointer' : 'default'}
                      _hover={column.sortable ? { bg: hoverBg } : undefined}
                      userSelect="none"
                      textAlign={column.isNumeric ? 'end' : 'start'}
                      width={column.width}
                      borderColor={borderColor}
                      aria-sort={column.sortable ? (sortBy === column.key ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
                    >
                      <HStack gap={2} justify={column.isNumeric ? 'flex-end' : 'flex-start'}>
                        <Text>{column.header}</Text>
                        {column.sortable && getSortIcon(column.key)}
                      </HStack>
                    </TableColumnHeader>
                  ))}
                </TableRow>
              </TableHeader>
            )}
            <TableBody>
              {sortedData.map((item, index) => (
                <TableRow
                  key={index}
                  _hover={{ bg: hoverBg }}
                  cursor={onRowClick ? 'pointer' : undefined}
                  onClick={onRowClick ? () => onRowClick(item) : undefined}
                  aria-label={onRowClick ? 'View details' : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            onRowClick(item);
                          }
                        }
                      : undefined
                  }
                >
                  {visibleColumns.map((column) => {
                    const value = column.accessor(item);
                    const renderedValue = column.render ? column.render(value, item) : value;

                    return (
                      <TableCell
                        key={column.key}
                        textAlign={column.isNumeric ? 'end' : 'start'}
                        borderColor={borderColor}
                      >
                        {renderedValue}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </TableRoot>
        </TableScrollArea>
        </Box>
      )}
    </Box>
  );
}

export default SortableTable; 