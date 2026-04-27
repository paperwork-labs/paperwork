"use client";

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  GripVertical,
  LayoutGrid,
  List,
  Loader2,
  Plus,
  Search,
  Zap,
} from 'lucide-react';
import {
  DndContext,
  DragOverlay,
  useSensor,
  useSensors,
  PointerSensor,
  closestCenter,
  useDroppable,
  useDraggable,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, useSortable, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ResponsiveModal as Dialog,
  ResponsiveModalContent as DialogContent,
  ResponsiveModalDescription as DialogDescription,
  ResponsiveModalFooter as DialogFooter,
  ResponsiveModalHeader as DialogHeader,
  ResponsiveModalTitle as DialogTitle,
} from '@/components/ui/responsive-modal';
import FormField from '@/components/ui/FormField';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import PageHeader from '@/components/ui/PageHeader';
import { portfolioApi, handleApiError } from '@/services/api';
import api from '@/services/api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCategories, useCategoryViews, useCategoryPositions, useRebalanceSuggestions } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';
import toast from 'react-hot-toast';
import { TableSkeleton } from '@/components/shared/Skeleton';
import SortableTable, { type Column } from '@/components/SortableTable';

type CategoryRow = {
  id: number;
  name: string;
  description?: string | null;
  color?: string | null;
  target_allocation_pct?: number | null;
  actual_allocation_pct?: number;
  positions_count?: number;
  total_value?: number;
};

type CatPosition = { id: number; symbol: string; market_value?: number; shares?: number; weight_pct?: number; stage_label?: string | null; unrealized_pnl?: number; unrealized_pnl_pct?: number };

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#14B8A6', '#F97316'];

/* ------------------------------------------------------------------ */
/*  DnD helpers                                                        */
/* ------------------------------------------------------------------ */

const DroppableCategory: React.FC<{ categoryId: number; children: React.ReactNode }> = ({ categoryId, children }) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `category-${categoryId}`,
    data: { categoryId },
  });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        'rounded-xl border-2 transition-[border-color] duration-200',
        isOver ? 'border-primary' : 'border-transparent',
      )}
    >
      {children}
    </div>
  );
};

const DraggableTicker: React.FC<{ positionId: number; symbol: string; categoryId: number; children: React.ReactNode }> = ({ positionId, symbol, categoryId, children }) => {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `pos-${positionId}`,
    data: { positionId, symbol, categoryId },
  });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn('inline-flex cursor-grab active:cursor-grabbing', isDragging && 'opacity-40')}
    >
      {children}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  AllocationChart – donut chart with legend                          */
/* ------------------------------------------------------------------ */

const AllocationChart: React.FC<{ categories: CategoryRow[]; currency: string }> = ({ categories, currency }) => {
  const data = categories
    .filter(c => (c.total_value ?? 0) > 0)
    .map(c => ({ name: c.name, value: Number(c.total_value ?? 0), target: Number(c.target_allocation_pct ?? 0), actual: Number(c.actual_allocation_pct ?? 0) }));

  if (data.length === 0) return null;

  return (
    <Card className="gap-0 py-0">
      <CardContent className="pt-6">
        <p className="mb-3 font-medium text-foreground">Allocation Overview</p>
        <div className="flex flex-wrap items-center gap-6">
          <div className="h-[200px] w-[200px] shrink-0">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => formatMoney(Number(value ?? 0), currency, { maximumFractionDigits: 0 })}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {data.map((d, i) => (
              <div key={d.name} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: COLORS[i % COLORS.length] }}
                    aria-hidden
                  />
                  <span>{d.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-muted-foreground">{d.actual.toFixed(1)}%</span>
                  {d.target > 0 ? (
                    <span
                      className={cn(
                        'font-mono text-xs',
                        Math.abs(d.actual - d.target) > 5 ? 'text-[rgb(var(--status-danger)/1)]' : 'text-muted-foreground',
                      )}
                    >
                      target {d.target}%
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

/* ------------------------------------------------------------------ */
/*  CategoryCard – single card with ticker chips                       */
/* ------------------------------------------------------------------ */

const CategoryCard: React.FC<{
  cat: CategoryRow;
  currency: string;
  onEdit: (cat: CategoryRow) => void;
  onAssign: (cat: CategoryRow) => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  isFirst?: boolean;
  isLast?: boolean;
  isDetailOpen?: boolean;
  onToggleDetail?: () => void;
}> = ({ cat, currency, onEdit, onAssign, onMoveUp, onMoveDown, isFirst, isLast, isDetailOpen, onToggleDetail }) => {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const target = Number(cat.target_allocation_pct ?? 0);
  const actual = Number(cat.actual_allocation_pct ?? 0);
  const diff = actual - target;

  const positionsQuery = useQuery({
    queryKey: ['categoryPositions', cat.id],
    queryFn: async () => {
      const res = await portfolioApi.getCategory(cat.id);
      const r = res as Record<string, any> | undefined;
      return (r?.data?.data?.positions ?? r?.data?.positions ?? r?.positions ?? []) as CatPosition[];
    },
    staleTime: 60_000,
  });
  const catPositions = positionsQuery.data ?? [];
  const PREVIEW_LIMIT = 12;
  const visiblePositions = expanded ? catPositions : catPositions.slice(0, PREVIEW_LIMIT);
  const overflowCount = catPositions.length - PREVIEW_LIMIT;

  const unassignMutation = useMutation({
    mutationFn: (positionId: number) => portfolioApi.unassignPosition(cat.id, positionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      queryClient.invalidateQueries({ queryKey: ['categoryPositions', cat.id] });
      toast.success('Position removed');
    },
    onError: (err) => { toast.error(`Failed to remove: ${handleApiError(err)}`); },
  });

  return (
    <Card className="gap-0 py-0">
      <CardContent className="pt-6">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <div className="flex flex-col gap-0">
              <button
                type="button"
                className={cn(
                  'p-0 leading-none text-muted-foreground',
                  isFirst ? 'cursor-default opacity-50' : 'cursor-pointer hover:text-foreground',
                )}
                onClick={isFirst ? undefined : onMoveUp}
                aria-label="Move up"
                disabled={isFirst}
              >
                <ChevronUp className="size-3.5" aria-hidden />
              </button>
              <button
                type="button"
                className={cn(
                  'p-0 leading-none text-muted-foreground',
                  isLast ? 'cursor-default opacity-50' : 'cursor-pointer hover:text-foreground',
                )}
                onClick={isLast ? undefined : onMoveDown}
                aria-label="Move down"
                disabled={isLast}
              >
                <ChevronDown className="size-3.5" aria-hidden />
              </button>
            </div>
            <button
              type="button"
              className="flex cursor-pointer items-center gap-1 text-left"
              onClick={onToggleDetail}
              aria-expanded={Boolean(isDetailOpen)}
            >
              <ChevronRight
                className={cn('size-3.5 shrink-0 text-muted-foreground transition-transform', isDetailOpen && 'rotate-90')}
                aria-hidden
              />
              <span className="font-semibold text-foreground">{cat.name}</span>
            </button>
          </div>
          {Math.abs(diff) > 5 ? (
            <Badge
              variant="secondary"
              className={cn(diff > 0 ? 'bg-destructive/15 text-destructive' : 'bg-amber-500/15 text-amber-700 dark:text-amber-400')}
            >
              Drift {diff > 0 ? '+' : ''}
              {diff.toFixed(1)}%
            </Badge>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          Target: {target}% · Actual: {actual.toFixed(1)}% · {cat.positions_count ?? 0} positions
        </p>
        <Progress value={actual} max={100} className="mt-2 h-2" />
        {diff !== 0 ? (
          <p
            className={cn(
              'mt-1 text-xs',
              diff < 0 ? 'text-[rgb(var(--status-warning)/1)]' : 'text-[rgb(var(--status-danger)/1)]',
            )}
          >
            {diff > 0 ? '+' : ''}
            {diff.toFixed(1)}% {diff < 0 ? 'underweight' : 'overweight'}
          </p>
        ) : null}
        {cat.total_value != null ? (
          <p className="mt-1 text-xs text-muted-foreground">
            {formatMoney(cat.total_value, currency, { maximumFractionDigits: 0 })}
          </p>
        ) : null}

        {isDetailOpen ? (
          <div className="mt-3 border-t border-border pt-2">
            {positionsQuery.isPending ? (
              <div className="flex items-center gap-2 py-2">
                <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
                <span className="text-xs text-muted-foreground">Loading positions…</span>
              </div>
            ) : catPositions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No positions in this category</p>
            ) : (
              <SortableTable<CatPosition>
                data={catPositions}
                columns={[
                  {
                    key: 'symbol',
                    header: 'Symbol',
                    accessor: (p) => p.symbol,
                    sortable: true,
                    sortType: 'string',
                    render: (v) => <span className="font-mono text-xs">{v}</span>,
                  },
                  {
                    key: 'shares',
                    header: 'Shares',
                    accessor: (p) => p.shares ?? 0,
                    sortable: true,
                    sortType: 'number',
                    isNumeric: true,
                    render: (v) => <span className="text-xs">{v != null ? Number(v).toFixed(2) : '—'}</span>,
                  },
                  {
                    key: 'market_value',
                    header: 'Value',
                    accessor: (p) => p.market_value ?? 0,
                    sortable: true,
                    sortType: 'number',
                    isNumeric: true,
                    render: (_, p) => (
                      <span className="text-xs">{formatMoney(p.market_value ?? 0, currency, { maximumFractionDigits: 0 })}</span>
                    ),
                  },
                  {
                    key: 'unrealized_pnl',
                    header: 'P&L',
                    accessor: (p) => p.unrealized_pnl ?? 0,
                    sortable: true,
                    sortType: 'number',
                    isNumeric: true,
                    render: (_, p) => (
                      <span
                        className={cn(
                          'text-xs',
                          (p.unrealized_pnl ?? 0) >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]',
                        )}
                      >
                        {formatMoney(p.unrealized_pnl ?? 0, currency, { maximumFractionDigits: 0 })}
                      </span>
                    ),
                  },
                  {
                    key: 'unrealized_pnl_pct',
                    header: 'P&L %',
                    accessor: (p) => p.unrealized_pnl_pct ?? 0,
                    sortable: true,
                    sortType: 'number',
                    isNumeric: true,
                    render: (_, p) => (
                      <span
                        className={cn(
                          'text-xs',
                          (p.unrealized_pnl_pct ?? 0) >= 0 ? 'text-[rgb(var(--status-success)/1)]' : 'text-[rgb(var(--status-danger)/1)]',
                        )}
                      >
                        {(p.unrealized_pnl_pct ?? 0).toFixed(1)}%
                      </span>
                    ),
                  },
                  {
                    key: 'weight_pct',
                    header: 'Weight',
                    accessor: (p) => p.weight_pct ?? 0,
                    sortable: true,
                    sortType: 'number',
                    isNumeric: true,
                    render: (v) => <span className="text-xs">{v != null ? `${Number(v).toFixed(1)}%` : '—'}</span>,
                  },
                  {
                    key: 'stage_label',
                    header: 'Stage',
                    accessor: (p) => p.stage_label ?? '',
                    sortable: true,
                    sortType: 'string',
                    render: (v) => (
                      <Badge variant="secondary" className="font-normal">
                        {v || '—'}
                      </Badge>
                    ),
                  },
                ] satisfies Column<CatPosition>[]}
                defaultSortBy="market_value"
                defaultSortOrder="desc"
                size="sm"
                emptyMessage="No positions in this category"
              />
            )}
          </div>
        ) : null}

        {!isDetailOpen && catPositions.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {visiblePositions.map((p) => (
              <DraggableTicker key={p.id} positionId={p.id} symbol={p.symbol} categoryId={cat.id}>
                <Badge
                  variant="outline"
                  className="cursor-pointer font-mono hover:border-destructive hover:text-destructive"
                  title={`Click to remove ${p.symbol} · Drag to move`}
                  onClick={() => unassignMutation.mutate(p.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      unassignMutation.mutate(p.id);
                    }
                  }}
                >
                  {p.symbol} ×
                </Badge>
              </DraggableTicker>
            ))}
            {overflowCount > 0 ? (
              <Badge
                variant="secondary"
                className="cursor-pointer hover:bg-muted"
                onClick={() => setExpanded(!expanded)}
                title={expanded ? 'Show fewer' : `Show all ${catPositions.length} tickers`}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setExpanded(!expanded);
                  }
                }}
              >
                {expanded ? 'Show less' : `+${overflowCount} more`}
              </Badge>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="xs" variant="outline" onClick={() => onEdit(cat)}>
            Edit
          </Button>
          <Button size="xs" variant="outline" onClick={() => onAssign(cat)}>
            Manage Positions
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

/* ------------------------------------------------------------------ */
/*  ManagePositionsDialog – clear membership, search, add/remove       */
/* ------------------------------------------------------------------ */

const ManagePositionsDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  categoryName: string;
  categoryId: number;
  allPositions: CatPosition[];
  uncategorizedIds: Set<number>;
  currency: string;
  pendingAdds: number[];
  pendingRemoves: number[];
  onToggleAdd: (id: number) => void;
  onToggleRemove: (id: number) => void;
  search: string;
  onSearchChange: (s: string) => void;
  onSave: () => void;
  isSaving: boolean;
  changeCount: number;
}> = ({
  open, onClose, categoryName, categoryId, allPositions, uncategorizedIds, currency,
  pendingAdds, pendingRemoves, onToggleAdd, onToggleRemove,
  search, onSearchChange, onSave, isSaving, changeCount,
}) => {
  const catPosQuery = useQuery({
    queryKey: ['categoryPositions', categoryId],
    queryFn: async () => {
      if (!categoryId) return [];
      const res = await portfolioApi.getCategory(categoryId);
      const r = res as Record<string, any> | undefined;
      return (r?.data?.data?.positions ?? r?.data?.positions ?? r?.positions ?? []) as CatPosition[];
    },
    staleTime: 60_000,
    enabled: open && categoryId > 0,
  });
  const currentMembers = catPosQuery.data ?? [];
  const memberIds = new Set(currentMembers.map(p => p.id));

  const effectiveMembers = currentMembers.filter(p => !pendingRemoves.includes(p.id));
  const newlyAdded = allPositions.filter(p => pendingAdds.includes(p.id));

  const uncatSet = uncategorizedIds ?? new Set<number>();
  const available = allPositions.filter(p => {
    if (pendingAdds.includes(p.id)) return false;
    if (memberIds.has(p.id) && !pendingRemoves.includes(p.id)) return false;
    if (pendingRemoves.includes(p.id)) return true;
    return uncatSet.has(p.id);
  });

  const lowerSearch = search.toLowerCase();
  const filteredAvailable = lowerSearch
    ? available.filter(p => p.symbol.toLowerCase().includes(lowerSearch))
    : available;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-lg gap-4 sm:max-w-lg" showCloseButton>
        <DialogHeader>
          <DialogTitle>Manage Positions · {categoryName}</DialogTitle>
          <DialogDescription>
            {effectiveMembers.length + newlyAdded.length} position
            {effectiveMembers.length + newlyAdded.length !== 1 ? 's' : ''} in category
          </DialogDescription>
        </DialogHeader>
        <div className="flex max-h-[min(70vh,520px)] flex-col gap-4 overflow-y-auto pr-1">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Check className="size-4 text-[rgb(var(--status-success)/1)]" aria-hidden />
              <span className="text-sm font-semibold">In this category</span>
            </div>
            {effectiveMembers.length === 0 && newlyAdded.length === 0 ? (
              <p className="pl-6 text-sm text-muted-foreground">No positions assigned yet</p>
            ) : (
              <div className="flex flex-wrap gap-1 pl-6">
                {effectiveMembers.map((p) => (
                  <Badge
                    key={p.id}
                    variant="default"
                    className="cursor-pointer bg-[rgb(var(--status-success)/1)] font-mono text-primary-foreground hover:opacity-90"
                    title={`Remove ${p.symbol} from category`}
                    onClick={() => onToggleRemove(p.id)}
                  >
                    {p.symbol}
                    {p.market_value != null ? (
                      <span className="ml-1 font-normal opacity-80">
                        {formatMoney(p.market_value, currency, { maximumFractionDigits: 0, notation: 'compact' })}
                      </span>
                    ) : null}{' '}
                    ×
                  </Badge>
                ))}
                {newlyAdded.map((p) => (
                  <Badge
                    key={p.id}
                    variant="outline"
                    className="cursor-pointer border-dashed border-[rgb(var(--status-success)/1)] font-mono text-[rgb(var(--status-success)/1)] hover:opacity-90"
                    title={`Undo adding ${p.symbol}`}
                    onClick={() => onToggleAdd(p.id)}
                  >
                    + {p.symbol} ×
                  </Badge>
                ))}
              </div>
            )}
            {pendingRemoves.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1 pl-6">
                <span className="text-xs text-[rgb(var(--status-danger)/1)]">Removing:</span>
                {pendingRemoves.map((id) => {
                  const p = currentMembers.find((m) => m.id === id);
                  return p ? (
                    <Badge
                      key={id}
                      variant="outline"
                      className="cursor-pointer font-mono line-through decoration-[rgb(var(--status-danger)/1)]"
                      onClick={() => onToggleRemove(id)}
                      title={`Undo remove ${p.symbol}`}
                    >
                      {p.symbol}
                    </Badge>
                  ) : null;
                })}
              </div>
            ) : null}
          </div>

          <div className="border-t border-border" role="separator" />

          <div>
            <div className="mb-2 flex items-center gap-2">
              <Plus className="size-4 text-primary" aria-hidden />
              <span className="text-sm font-semibold">Add positions</span>
            </div>
            <div className="relative mb-2 pl-6">
              <Search
                className="pointer-events-none absolute top-1/2 left-9 z-[1] size-3.5 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                className="h-8 pl-8 text-sm"
                placeholder="Search by ticker..."
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </div>
            <div className="max-h-[200px] overflow-y-auto pl-6">
              {filteredAvailable.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {search ? 'No matching positions' : 'All positions are assigned to this category'}
                </p>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {filteredAvailable.map((p) => (
                    <Badge
                      key={p.id}
                      variant="outline"
                      className="cursor-pointer font-mono hover:border-primary hover:text-primary"
                      title={`Add ${p.symbol} to ${categoryName}`}
                      onClick={() => onToggleAdd(p.id)}
                    >
                      + {p.symbol}
                      {p.market_value != null ? (
                        <span className="ml-1 font-normal opacity-70">
                          {formatMoney(p.market_value, currency, { maximumFractionDigits: 0, notation: 'compact' })}
                        </span>
                      ) : null}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={onSave} disabled={changeCount === 0 || isSaving}>
            {isSaving ? 'Saving...' : changeCount === 0 ? 'No changes' : `Save ${changeCount} change${changeCount !== 1 ? 's' : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/* ------------------------------------------------------------------ */
/*  SortableTableRow – draggable row for table view reorder            */
/* ------------------------------------------------------------------ */

const SortableTableRow: React.FC<{
  cat: CategoryRow;
  currency: string;
  onEdit: (cat: CategoryRow) => void;
  onAssign: (cat: CategoryRow) => void;
}> = ({ cat, currency, onEdit, onAssign }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: cat.id,
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  const target = Number(cat.target_allocation_pct ?? 0);
  const actual = Number(cat.actual_allocation_pct ?? 0);
  const drift = actual - target;

  return (
    <tr ref={setNodeRef} style={style} className={cn('border-b border-border', isDragging && 'bg-muted')}>
      <td className="w-10 px-2 align-middle">
        <div
          {...attributes}
          {...listeners}
          className="flex cursor-grab items-center text-muted-foreground active:cursor-grabbing hover:text-foreground"
        >
          <GripVertical className="size-[18px]" aria-hidden />
        </div>
      </td>
      <td className="px-3 py-2 align-middle font-semibold">{cat.name}</td>
      <td className="px-3 py-2 text-right align-middle tabular-nums">{target}%</td>
      <td className="px-3 py-2 text-right align-middle tabular-nums">{actual.toFixed(1)}%</td>
      <td
        className={cn(
          'px-3 py-2 text-right align-middle tabular-nums',
          Math.abs(drift) > 5 ? 'text-[rgb(var(--status-danger)/1)]' : drift !== 0 ? 'text-[rgb(var(--status-warning)/1)]' : 'text-muted-foreground',
        )}
      >
        {drift > 0 ? '+' : ''}
        {drift.toFixed(1)}%
      </td>
      <td className="px-3 py-2 text-right align-middle tabular-nums">{cat.positions_count ?? 0}</td>
      <td className="px-3 py-2 text-right align-middle tabular-nums">
        {formatMoney(cat.total_value ?? 0, currency, { maximumFractionDigits: 0 })}
      </td>
      <td className="px-3 py-2 align-middle">
        <div className="flex flex-wrap gap-1">
          <Button size="xs" variant="outline" onClick={() => onEdit(cat)}>
            Edit
          </Button>
          <Button size="xs" variant="outline" onClick={() => onAssign(cat)}>
            Assign
          </Button>
        </div>
      </td>
    </tr>
  );
};

/* ------------------------------------------------------------------ */
/*  Auto-categorize presets                                            */
/* ------------------------------------------------------------------ */

const PRESETS = [
  { id: 'sector', label: 'By Sector', description: 'Group by GICS sector (Technology, Healthcare, etc.)' },
  { id: 'market_cap', label: 'By Market Cap', description: 'Mega Cap, Large Cap, Mid Cap, Small Cap, Micro Cap' },
  { id: 'stage', label: 'By Weinstein Stage', description: 'Stage 1 (Accumulation) through Stage 4 (Decline)' },
  { id: 'rs_quartile', label: 'By RS Percentile', description: 'Quartiles based on relative strength vs market' },
] as const;

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

const VIEW_LABELS: Record<string, string> = {
  custom: 'Personalized',
  sector: 'By Sector',
  market_cap: 'By Market Cap',
  stage: 'By Stage',
  rs_quartile: 'By RS Percentile',
};

const FIXED_TABS = [
  { key: 'sector', label: 'Sector' },
  { key: 'market_cap', label: 'Market Cap' },
  { key: 'stage', label: 'Stage' },
  { key: 'custom', label: 'Custom' },
] as const;

const PortfolioCategoriesClient: React.FC = () => {
  const { currency } = useUserPreferences();
  const queryClient = useQueryClient();

  const [activeView, setActiveView] = useState<string>('sector');
  const [view, setView] = useState<'card' | 'table'>('card');
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<CategoryRow | null>(null);
  const [newName, setNewName] = useState('');
  const [newTargetPct, setNewTargetPct] = useState<string>('');
  const [assignSearch, setAssignSearch] = useState('');
  const [pendingAdds, setPendingAdds] = useState<number[]>([]);
  const [pendingRemoves, setPendingRemoves] = useState<number[]>([]);
  const [detailCatId, setDetailCatId] = useState<number | null>(null);

  const appliedPresetsRef = useRef(new Set<string>());

  useCategoryViews();

  const { data: categoriesData, isPending } = useCategories(activeView);
  const categories = (categoriesData?.categories ?? []) as CategoryRow[];
  const uncategorized = categoriesData?.uncategorized ?? { positions_count: 0, total_value: 0, actual_allocation_pct: 0, position_ids: [] };

  const rebalanceQuery = useRebalanceSuggestions();
  const rebalanceData = rebalanceQuery.data ?? {};
  const suggestions = rebalanceData.suggestions ?? [];

  const { data: positionsData } = useCategoryPositions();
  const allPositions = positionsData ?? [];

  const uncategorizedIds = useMemo(
    () => new Set<number>(uncategorized.position_ids ?? []),
    [uncategorized.position_ids],
  );

  /* ---------- mutations ---------- */

  const createMutation = useMutation({
    mutationFn: () => {
      const target = newTargetPct ? parseFloat(newTargetPct) : undefined;
      return portfolioApi.createCategory({
        name: newName.trim(),
        target_allocation_pct: target,
        category_type: activeView,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioCategoryViews'] });
      toast.success('Category created');
      setNewName('');
      setNewTargetPct('');
      setCreateOpen(false);
    },
    onError: (err) => { toast.error(`Failed to create category: ${handleApiError(err)}`); },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!selectedCategory) throw new Error('No category selected');
      const target = newTargetPct ? parseFloat(newTargetPct) : undefined;
      return portfolioApi.updateCategory(selectedCategory.id, { name: newName.trim(), target_allocation_pct: target });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      toast.success('Category updated');
      setEditOpen(false);
      setSelectedCategory(null);
    },
    onError: (err) => { toast.error(`Failed to update category: ${handleApiError(err)}`); },
  });

  const assignMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCategory) throw new Error('No category selected');
      const catId = selectedCategory.id;
      for (const posId of pendingRemoves) {
        await portfolioApi.unassignPosition(catId, posId);
      }
      if (pendingAdds.length > 0) {
        await portfolioApi.assignPositions(catId, pendingAdds);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      if (selectedCategory) queryClient.invalidateQueries({ queryKey: ['categoryPositions', selectedCategory.id] });
      const total = pendingAdds.length + pendingRemoves.length;
      toast.success(`Updated ${total} position(s)`);
      setAssignOpen(false);
      setSelectedCategory(null);
    },
    onError: (err) => { toast.error(`Failed to update positions: ${handleApiError(err)}`); },
  });

  const applyPresetMutation = useMutation({
    mutationFn: (presetId: string) => api.post('/portfolio/categories/apply-preset', { preset: presetId }),
    onSuccess: (_data, presetId) => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioCategoryViews'] });
      setActiveView(presetId);
      toast.success(`Switched to ${VIEW_LABELS[presetId] ?? presetId} view`);
      setPresetOpen(false);
    },
    onError: (err) => { toast.error(`Failed to apply preset: ${handleApiError(err)}`); },
  });

  // Auto-apply preset when switching to a non-custom tab with no (or empty) categories
  useEffect(() => {
    if (activeView === 'custom') return;
    if (isPending) return;
    if (appliedPresetsRef.current.has(activeView)) return;
    const cats = (categoriesData?.categories ?? []) as CategoryRow[];
    const totalAssigned = cats.reduce((s, c) => s + (c.positions_count ?? 0), 0);
    if (cats.length === 0 || totalAssigned === 0) {
      appliedPresetsRef.current.add(activeView);
      applyPresetMutation.mutate(activeView);
    }
  }, [activeView, isPending, categoriesData]);

  const moveMutation = useMutation({
    mutationFn: async (args: { positionId: number; fromCategoryId: number; toCategoryId: number }) => {
      await api.delete(`/portfolio/categories/${args.fromCategoryId}/positions/${args.positionId}`);
      await api.post(`/portfolio/categories/${args.toCategoryId}/positions`, {
        position_ids: [args.positionId],
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
      queryClient.invalidateQueries({ queryKey: ['categoryPositions'] });
      toast.success('Position moved');
    },
    onError: (err) => { toast.error(`Failed to move: ${handleApiError(err)}`); },
  });

  const reorderMutation = useMutation({
    mutationFn: (orderedIds: number[]) => portfolioApi.reorderCategories(orderedIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolioCategories'] });
    },
    onError: (err) => { toast.error(`Failed to reorder: ${handleApiError(err)}`); },
  });

  const persistOrder = useCallback((newCategories: CategoryRow[]) => {
    reorderMutation.mutate(newCategories.map(c => c.id));
  }, [reorderMutation]);

  const moveCategory = useCallback((fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= categories.length) return;
    const reordered = arrayMove([...categories], fromIndex, toIndex);
    persistOrder(reordered);
  }, [categories, persistOrder]);

  /* ---------- DnD ---------- */

  const [activeDrag, setActiveDrag] = useState<{ positionId: number; symbol: string; fromCategoryId: number } | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const data = active.data.current as { positionId: number; symbol: string; categoryId: number } | undefined;
    if (data) {
      setActiveDrag({ positionId: data.positionId, symbol: data.symbol, fromCategoryId: data.categoryId });
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { over } = event;
    if (!activeDrag || !over) {
      setActiveDrag(null);
      return;
    }
    const toCategoryId = over.data.current?.categoryId as number | undefined;
    if (toCategoryId && toCategoryId !== activeDrag.fromCategoryId) {
      moveMutation.mutate({
        positionId: activeDrag.positionId,
        fromCategoryId: activeDrag.fromCategoryId,
        toCategoryId,
      });
    }
    setActiveDrag(null);
  };

  const handleTableDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = categories.findIndex(c => c.id === active.id);
    const newIndex = categories.findIndex(c => c.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const reordered = arrayMove([...categories], oldIndex, newIndex);
    persistOrder(reordered);
  }, [categories, persistOrder]);

  const tableSortableIds = useMemo(() => categories.map(c => c.id), [categories]);

  /* ---------- handlers ---------- */

  const handleCreate = () => createMutation.mutate();
  const handleUpdate = () => updateMutation.mutate();
  const handleSaveAssignments = () => assignMutation.mutate();

  const openEdit = (cat: CategoryRow) => {
    setSelectedCategory(cat);
    setNewName(cat.name);
    setNewTargetPct(cat.target_allocation_pct != null ? String(cat.target_allocation_pct) : '');
    setEditOpen(true);
  };

  const openAssign = (cat: CategoryRow) => {
    setSelectedCategory(cat);
    setPendingAdds([]);
    setPendingRemoves([]);
    setAssignSearch('');
    setAssignOpen(true);
  };

  /* ---------- render ---------- */

  return (
    <div className="p-4">
      <div className="flex flex-col gap-4">
        <PageHeader
          title="Categories"
          subtitle="Target allocations and position assignment"
          rightContent={
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => setPresetOpen(true)}>
                <Zap className="size-4" aria-hidden />
                Auto-Categorize
              </Button>

              <div className="flex gap-1">
                <Button
                  size="xs"
                  variant={view === 'card' ? 'default' : 'ghost'}
                  onClick={() => setView('card')}
                  aria-label="Card view"
                  aria-pressed={view === 'card'}
                >
                  <LayoutGrid className="size-4" />
                </Button>
                <Button
                  size="xs"
                  variant={view === 'table' ? 'default' : 'ghost'}
                  onClick={() => setView('table')}
                  aria-label="Table view"
                  aria-pressed={view === 'table'}
                >
                  <List className="size-4" />
                </Button>
              </div>

              <Button
                onClick={() => {
                  setNewName('');
                  setNewTargetPct('');
                  setCreateOpen(true);
                }}
              >
                + New Category
              </Button>
            </div>
          }
        />

        <div className="flex flex-wrap gap-0 rounded-lg border border-border bg-muted/40 p-1">
          {FIXED_TABS.map((tab) => {
            const isActive = activeView === tab.key;
            return (
              <Button
                key={tab.key}
                size="sm"
                variant={isActive ? 'default' : 'ghost'}
                className={cn(
                  'min-w-0 rounded-md px-4',
                  isActive && 'bg-amber-500 font-semibold text-white hover:bg-amber-400',
                )}
                onClick={() => {
                  setActiveView(tab.key);
                  setDetailCatId(null);
                }}
              >
                {tab.label}
              </Button>
            );
          })}
        </div>

        {categories.length > 0 ? <AllocationChart categories={categories} currency={currency} /> : null}

        {isPending || (activeView !== 'custom' && applyPresetMutation.isPending) ? (
          <TableSkeleton rows={5} cols={4} />
        ) : categories.length === 0 ? (
          <Card className="gap-0 py-0">
            <CardContent className="py-8">
              <div className="flex flex-col gap-2">
                <p className="text-muted-foreground">
                  {activeView === 'custom'
                    ? 'No categories yet. Create one to group positions and track target allocation.'
                    : `No categories in this view. Use Auto-Categorize to create "${VIEW_LABELS[activeView] ?? activeView}" categories.`}
                </p>
                {activeView !== 'custom' ? (
                  <Button size="sm" variant="outline" onClick={() => applyPresetMutation.mutate(activeView)}>
                    <Zap className="size-4" aria-hidden />
                    Auto-Categorize
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : view === 'table' ? (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleTableDragEnd}>
            <SortableContext items={tableSortableIds} strategy={verticalListSortingStrategy}>
              <Card className="gap-0 overflow-hidden py-0">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        <th className="h-10 w-10 px-2 text-left font-medium" />
                        <th className="px-3 py-2 text-left font-medium">Category</th>
                        <th className="px-3 py-2 text-right font-medium">Target %</th>
                        <th className="px-3 py-2 text-right font-medium">Actual %</th>
                        <th className="px-3 py-2 text-right font-medium">Drift</th>
                        <th className="px-3 py-2 text-right font-medium">Positions</th>
                        <th className="px-3 py-2 text-right font-medium">Value</th>
                        <th className="px-3 py-2 text-left font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {categories.map((cat) => (
                        <SortableTableRow
                          key={cat.id}
                          cat={cat}
                          currency={currency}
                          onEdit={openEdit}
                          onAssign={openAssign}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </SortableContext>
          </DndContext>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {categories.map((cat, idx) => (
                <DroppableCategory key={cat.id} categoryId={cat.id}>
                  <CategoryCard
                    cat={cat}
                    currency={currency}
                    onEdit={openEdit}
                    onAssign={openAssign}
                    onMoveUp={() => moveCategory(idx, idx - 1)}
                    onMoveDown={() => moveCategory(idx, idx + 1)}
                    isFirst={idx === 0}
                    isLast={idx === categories.length - 1}
                    isDetailOpen={detailCatId === cat.id}
                    onToggleDetail={() => setDetailCatId((prev) => (prev === cat.id ? null : cat.id))}
                  />
                </DroppableCategory>
              ))}
            </div>
            <DragOverlay>
              {activeDrag ? (
                <Badge variant="default" className="font-mono">
                  {activeDrag.symbol}
                </Badge>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}

        {uncategorized.positions_count > 0 ? (
          <Card className="gap-0 border-dashed py-0">
            <CardContent className="pt-6">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <Badge variant="secondary">Uncategorized</Badge>
                  <span className="font-semibold text-muted-foreground">
                    {uncategorized.positions_count} position{uncategorized.positions_count !== 1 ? 's' : ''} not in any{' '}
                    {VIEW_LABELS[activeView] ?? activeView} category
                  </span>
                </div>
                <span className="font-mono text-sm text-muted-foreground">
                  {formatMoney(uncategorized.total_value, currency, { maximumFractionDigits: 0 })}
                  {' · '}
                  {uncategorized.actual_allocation_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {allPositions
                  .filter((p) => uncategorized.position_ids?.includes(p.id))
                  .slice(0, 20)
                  .map((p) => (
                    <Badge key={p.id} variant="outline" className="font-mono">
                      {p.symbol}
                    </Badge>
                  ))}
                {uncategorized.positions_count > 20 ? (
                  <Badge variant="secondary">+{uncategorized.positions_count - 20} more</Badge>
                ) : null}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Assign these positions to categories above using &quot;Manage Positions&quot;, or drag them in card view.
              </p>
            </CardContent>
          </Card>
        ) : null}

        {suggestions.length > 0 ? (
          <Card className="gap-0 py-0">
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-base">Rebalancing Preview</CardTitle>
                <Badge variant="secondary" className="bg-amber-500/15 text-amber-800 dark:text-amber-300">
                  {suggestions.length} adjustments
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-2">
              <div className="mb-4 flex flex-wrap items-start gap-6">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-xs font-bold text-muted-foreground">CURRENT</span>
                  <div className="h-[120px] w-[120px]">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={categories
                            .filter((c) => (c.actual_allocation_pct ?? 0) > 0)
                            .map((c) => ({ name: c.name, value: Number(c.actual_allocation_pct ?? 0) }))}
                          dataKey="value"
                          innerRadius={30}
                          outerRadius={50}
                          paddingAngle={2}
                        >
                          {categories.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span className="text-xs font-bold text-muted-foreground">TARGET</span>
                  <div className="h-[120px] w-[120px]">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={categories
                            .filter((c) => (c.target_allocation_pct ?? 0) > 0)
                            .map((c) => ({ name: c.name, value: Number(c.target_allocation_pct ?? 0) }))}
                          dataKey="value"
                          innerRadius={30}
                          outerRadius={50}
                          paddingAngle={2}
                        >
                          {categories.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-3">
                {suggestions.map((s: { category: string; direction: string; amount: number; target_pct: number; actual_pct: number; drift_pct: number; positions?: Array<{ symbol: string; shares: number; est_value: number }> }, i: number) => (
                  <div key={i} className="rounded-lg border border-border p-3">
                    <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{s.category}</span>
                        <Badge
                          variant="secondary"
                          className={
                            s.direction === 'BUY'
                              ? 'bg-[rgb(var(--status-success)/0.15)] text-[rgb(var(--status-success)/1)]'
                              : 'bg-destructive/15 text-destructive'
                          }
                        >
                          {s.direction}
                        </Badge>
                      </div>
                      <span className="text-sm font-bold">{formatMoney(s.amount, currency, { maximumFractionDigits: 0 })}</span>
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>Target: {s.target_pct}%</span>
                      <span>Actual: {s.actual_pct}%</span>
                      <span className={Math.abs(s.drift_pct) > 5 ? 'text-[rgb(var(--status-danger)/1)]' : ''}>
                        Drift: {s.drift_pct > 0 ? '+' : ''}
                        {s.drift_pct}%
                      </span>
                    </div>
                    {s.positions != null && s.positions.length > 0 ? (
                      <div className="mt-2">
                        {s.positions.map((p, j) => (
                          <div key={j} className="flex justify-between py-0.5 text-xs">
                            <span className="font-mono">{p.symbol}</span>
                            <span>
                              {p.shares > 0 ? `~${p.shares} sh` : ''} · {formatMoney(p.est_value, currency, { maximumFractionDigits: 0 })}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="gap-4" showCloseButton>
          <DialogHeader>
            <DialogTitle>New Category</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <FormField label="Name" required>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Growth" />
            </FormField>
            <FormField label="Target allocation %" required={false}>
              <Input type="number" value={newTargetPct} onChange={(e) => setNewTargetPct(e.target.value)} placeholder="e.g. 40" />
            </FormField>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleCreate} disabled={!newName.trim() || createMutation.isPending}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={(o) => !o && setEditOpen(false)}>
        <DialogContent className="gap-4" showCloseButton>
          <DialogHeader>
            <DialogTitle>Edit Category</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <FormField label="Name" required>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} />
            </FormField>
            <FormField label="Target allocation %" required={false}>
              <Input type="number" value={newTargetPct} onChange={(e) => setNewTargetPct(e.target.value)} />
            </FormField>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleUpdate} disabled={!newName.trim() || updateMutation.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ManagePositionsDialog
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        categoryName={selectedCategory?.name ?? ''}
        categoryId={selectedCategory?.id ?? 0}
        allPositions={allPositions}
        uncategorizedIds={uncategorizedIds}
        currency={currency}
        pendingAdds={pendingAdds}
        pendingRemoves={pendingRemoves}
        onToggleAdd={(id) => setPendingAdds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
        onToggleRemove={(id) => setPendingRemoves((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
        search={assignSearch}
        onSearchChange={setAssignSearch}
        onSave={handleSaveAssignments}
        isSaving={assignMutation.isPending}
        changeCount={pendingAdds.length + pendingRemoves.length}
      />

      <Dialog open={presetOpen} onOpenChange={setPresetOpen}>
        <DialogContent className="max-w-2xl gap-4" showCloseButton>
          <DialogHeader>
            <DialogTitle>Auto-Categorize Positions</DialogTitle>
            <DialogDescription>
              Choose a preset to automatically create categories and assign positions. Existing categories will not be removed.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className={cn(
                  'rounded-lg border border-border p-4 text-left transition-colors hover:border-primary hover:bg-muted/50',
                  applyPresetMutation.isPending && 'pointer-events-none opacity-50',
                )}
                onClick={() => applyPresetMutation.mutate(preset.id)}
              >
                <p className="mb-1 font-semibold">{preset.label}</p>
                <p className="text-xs text-muted-foreground">{preset.description}</p>
              </button>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPresetOpen(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PortfolioCategoriesClient;
