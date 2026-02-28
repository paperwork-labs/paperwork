import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Box,
  Text,
  Stack,
  HStack,
  Button,
  CardRoot,
  CardHeader,
  CardBody,
  VStack,
  SimpleGrid,
  Table,
  DialogRoot,
  DialogBackdrop,
  DialogPositioner,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogCloseTrigger,
  Input,
  Field,
  Progress,
  Badge,
  Icon,
  Spinner,
  Collapsible,
} from '@chakra-ui/react';
import { FiGrid, FiList, FiZap, FiSearch, FiPlus, FiCheck, FiChevronUp, FiChevronDown, FiChevronRight } from 'react-icons/fi';
import { RiDraggable } from 'react-icons/ri';
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
import PageHeader from '../../components/ui/PageHeader';
import { portfolioApi, handleApiError } from '../../services/api';
import api from '../../services/api';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { useCategories, useCategoryViews, useCategoryPositions, useRebalanceSuggestions } from '../../hooks/usePortfolio';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';
import toast from 'react-hot-toast';
import { TableSkeleton } from '../../components/shared/Skeleton';

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
    <Box
      ref={setNodeRef}
      borderWidth="2px"
      borderColor={isOver ? 'brand.500' : 'transparent'}
      borderRadius="xl"
      transition="border-color 0.2s"
    >
      {children}
    </Box>
  );
};

const DraggableTicker: React.FC<{ positionId: number; symbol: string; categoryId: number; children: React.ReactNode }> = ({ positionId, symbol, categoryId, children }) => {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `pos-${positionId}`,
    data: { positionId, symbol, categoryId },
  });
  return (
    <Box
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      opacity={isDragging ? 0.4 : 1}
      cursor="grab"
      _active={{ cursor: 'grabbing' }}
      display="inline-flex"
    >
      {children}
    </Box>
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
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody>
        <Text fontWeight="bold" mb={3}>Allocation Overview</Text>
        <HStack gap={6} align="center" flexWrap="wrap">
          <Box w="200px" h="200px">
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
          </Box>
          <VStack align="stretch" gap={1} flex={1}>
            {data.map((d, i) => (
              <HStack key={d.name} justify="space-between" fontSize="sm">
                <HStack gap={2}>
                  <Box w="10px" h="10px" borderRadius="full" bg={COLORS[i % COLORS.length]} flexShrink={0} />
                  <Text>{d.name}</Text>
                </HStack>
                <HStack gap={3}>
                  <Text fontFamily="mono" color="fg.muted">{d.actual.toFixed(1)}%</Text>
                  {d.target > 0 && (
                    <Text fontFamily="mono" color={Math.abs(d.actual - d.target) > 5 ? 'fg.error' : 'fg.muted'} fontSize="xs">
                      target {d.target}%
                    </Text>
                  )}
                </HStack>
              </HStack>
            ))}
          </VStack>
        </HStack>
      </CardBody>
    </CardRoot>
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

  const positionsQuery = useQuery(
    ['categoryPositions', cat.id],
    async () => {
      const res = await portfolioApi.getCategory(cat.id);
      const r = res as Record<string, any> | undefined;
      return (r?.data?.data?.positions ?? r?.data?.positions ?? r?.positions ?? []) as CatPosition[];
    },
    { staleTime: 60_000 },
  );
  const catPositions = positionsQuery.data ?? [];
  const PREVIEW_LIMIT = 12;
  const visiblePositions = expanded ? catPositions : catPositions.slice(0, PREVIEW_LIMIT);
  const overflowCount = catPositions.length - PREVIEW_LIMIT;

  const unassignMutation = useMutation(
    (positionId: number) => portfolioApi.unassignPosition(cat.id, positionId),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        queryClient.invalidateQueries(['categoryPositions', cat.id]);
        toast.success('Position removed');
      },
      onError: (err) => { toast.error(`Failed to remove: ${handleApiError(err)}`); },
    },
  );

  return (
    <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
      <CardBody>
        <HStack justify="space-between" align="center" mb={2}>
          <HStack gap={1}>
            <VStack gap={0}>
              <Box
                as="button"
                p={0}
                lineHeight={1}
                fontSize="xs"
                color={isFirst ? 'fg.subtle' : 'fg.muted'}
                cursor={isFirst ? 'default' : 'pointer'}
                _hover={isFirst ? {} : { color: 'fg.default' }}
                onClick={isFirst ? undefined : onMoveUp}
                aria-label="Move up"
              >
                <FiChevronUp size={14} />
              </Box>
              <Box
                as="button"
                p={0}
                lineHeight={1}
                fontSize="xs"
                color={isLast ? 'fg.subtle' : 'fg.muted'}
                cursor={isLast ? 'default' : 'pointer'}
                _hover={isLast ? {} : { color: 'fg.default' }}
                onClick={isLast ? undefined : onMoveDown}
                aria-label="Move down"
              >
                <FiChevronDown size={14} />
              </Box>
            </VStack>
            <Box
              cursor="pointer"
              onClick={onToggleDetail}
              display="flex"
              alignItems="center"
              gap={1}
            >
              <Box
                transform={isDetailOpen ? 'rotate(90deg)' : undefined}
                transition="transform 0.15s"
                color="fg.muted"
              >
                <FiChevronRight size={14} />
              </Box>
              <Text fontWeight="semibold">{cat.name}</Text>
            </Box>
          </HStack>
          {Math.abs(diff) > 5 && (
            <Badge colorPalette={diff > 0 ? 'red' : 'orange'} size="sm">
              Drift {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
            </Badge>
          )}
        </HStack>
        <Text fontSize="sm" color="fg.muted">
          Target: {target}% · Actual: {actual.toFixed(1)}% · {cat.positions_count ?? 0} positions
        </Text>
        <Progress.Root value={actual} max={100} size="sm" mt={2} borderRadius="md">
          <Progress.Track>
            <Progress.Range bg="brand.500" />
          </Progress.Track>
        </Progress.Root>
        {diff !== 0 && (
          <Text fontSize="xs" color={diff < 0 ? 'status.warning' : 'status.danger'} mt={1}>
            {diff > 0 ? '+' : ''}{diff.toFixed(1)}% {diff < 0 ? 'underweight' : 'overweight'}
          </Text>
        )}
        {cat.total_value != null && (
          <Text fontSize="xs" color="fg.muted" mt={1}>
            {formatMoney(cat.total_value, currency, { maximumFractionDigits: 0 })}
          </Text>
        )}

        {/* Click-through detail table */}
        {isDetailOpen && (
          <Box mt={3} borderTopWidth="1px" borderColor="border.subtle" pt={2}>
            {positionsQuery.isLoading ? (
              <HStack gap={2} py={2}><Spinner size="xs" /><Text fontSize="xs" color="fg.muted">Loading positions…</Text></HStack>
            ) : catPositions.length === 0 ? (
              <Text fontSize="xs" color="fg.muted">No positions in this category</Text>
            ) : (
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Symbol</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="right">Shares</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="right">Value</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="right">P&L</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="right">P&L %</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="right">Weight</Table.ColumnHeader>
                    <Table.ColumnHeader>Stage</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {catPositions.map((p) => (
                    <Table.Row key={p.id}>
                      <Table.Cell><Text fontFamily="mono" fontSize="xs">{p.symbol}</Text></Table.Cell>
                      <Table.Cell textAlign="right"><Text fontSize="xs">{p.shares != null ? p.shares.toFixed(2) : '—'}</Text></Table.Cell>
                      <Table.Cell textAlign="right"><Text fontSize="xs">{formatMoney(p.market_value ?? 0, currency, { maximumFractionDigits: 0 })}</Text></Table.Cell>
                      <Table.Cell textAlign="right">
                        <Text fontSize="xs" color={(p.unrealized_pnl ?? 0) >= 0 ? 'fg.success' : 'fg.error'}>
                          {formatMoney(p.unrealized_pnl ?? 0, currency, { maximumFractionDigits: 0 })}
                        </Text>
                      </Table.Cell>
                      <Table.Cell textAlign="right">
                        <Text fontSize="xs" color={(p.unrealized_pnl_pct ?? 0) >= 0 ? 'fg.success' : 'fg.error'}>
                          {(p.unrealized_pnl_pct ?? 0).toFixed(1)}%
                        </Text>
                      </Table.Cell>
                      <Table.Cell textAlign="right"><Text fontSize="xs">{p.weight_pct != null ? `${p.weight_pct.toFixed(1)}%` : '—'}</Text></Table.Cell>
                      <Table.Cell><Badge size="sm" variant="subtle">{p.stage_label || '—'}</Badge></Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            )}
          </Box>
        )}

        {!isDetailOpen && catPositions.length > 0 && (
          <HStack mt={2} gap={1} flexWrap="wrap">
            {visiblePositions.map((p) => (
              <DraggableTicker key={p.id} positionId={p.id} symbol={p.symbol} categoryId={cat.id}>
                <Badge
                  size="sm"
                  variant="outline"
                  colorPalette="gray"
                  fontFamily="mono"
                  cursor="pointer"
                  title={`Click to remove ${p.symbol} · Drag to move`}
                  onClick={() => unassignMutation.mutate(p.id)}
                  _hover={{ colorPalette: 'red', borderColor: 'red.400' }}
                >
                  {p.symbol} ×
                </Badge>
              </DraggableTicker>
            ))}
            {overflowCount > 0 && (
              <Badge
                size="sm"
                variant="subtle"
                colorPalette="brand"
                cursor="pointer"
                _hover={{ bg: 'brand.100', _dark: { bg: 'brand.900' } }}
                onClick={() => setExpanded(!expanded)}
                title={expanded ? 'Show fewer' : `Show all ${catPositions.length} tickers`}
              >
                {expanded ? 'Show less' : `+${overflowCount} more`}
              </Badge>
            )}
          </HStack>
        )}

        <HStack mt={3} gap={2}>
          <Button size="xs" variant="outline" onClick={() => onEdit(cat)}>Edit</Button>
          <Button size="xs" variant="outline" onClick={() => onAssign(cat)}>Manage Positions</Button>
        </HStack>
      </CardBody>
    </CardRoot>
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
  const catPosQuery = useQuery(
    ['categoryPositions', categoryId],
    async () => {
      if (!categoryId) return [];
      const res = await portfolioApi.getCategory(categoryId);
      const r = res as Record<string, any> | undefined;
      return (r?.data?.data?.positions ?? r?.data?.positions ?? r?.positions ?? []) as CatPosition[];
    },
    { staleTime: 60_000, enabled: open && categoryId > 0 },
  );
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
    <DialogRoot open={open} onOpenChange={(e) => { if (!e.open) onClose(); }}>
      <DialogBackdrop />
      <DialogPositioner>
        <DialogContent maxW="lg">
          <DialogHeader>
            <VStack align="stretch" gap={1}>
              <Text fontSize="lg" fontWeight="bold">Manage Positions · {categoryName}</Text>
              <Text fontSize="sm" color="fg.muted">
                {effectiveMembers.length + newlyAdded.length} position{effectiveMembers.length + newlyAdded.length !== 1 ? 's' : ''} in category
              </Text>
            </VStack>
          </DialogHeader>
          <DialogBody>
            <VStack align="stretch" gap={4}>
              {/* Current members */}
              <Box>
                <HStack mb={2} gap={2}>
                  <FiCheck color="var(--chakra-colors-green-500)" />
                  <Text fontSize="sm" fontWeight="semibold">In this category</Text>
                </HStack>
                {effectiveMembers.length === 0 && newlyAdded.length === 0 ? (
                  <Text fontSize="sm" color="fg.muted" pl={6}>No positions assigned yet</Text>
                ) : (
                  <HStack gap={1} flexWrap="wrap" pl={6}>
                    {effectiveMembers.map(p => (
                      <Badge
                        key={p.id}
                        size="sm"
                        variant="solid"
                        colorPalette="green"
                        fontFamily="mono"
                        cursor="pointer"
                        title={`Remove ${p.symbol} from category`}
                        onClick={() => onToggleRemove(p.id)}
                        _hover={{ opacity: 0.7 }}
                      >
                        {p.symbol}
                        {p.market_value != null && (
                          <Text as="span" ml={1} fontWeight="normal" opacity={0.8}>
                            {formatMoney(p.market_value, currency, { maximumFractionDigits: 0, notation: 'compact' })}
                          </Text>
                        )}
                        {' '}×
                      </Badge>
                    ))}
                    {newlyAdded.map(p => (
                      <Badge
                        key={p.id}
                        size="sm"
                        variant="outline"
                        colorPalette="green"
                        fontFamily="mono"
                        cursor="pointer"
                        borderStyle="dashed"
                        title={`Undo adding ${p.symbol}`}
                        onClick={() => onToggleAdd(p.id)}
                        _hover={{ opacity: 0.7 }}
                      >
                        + {p.symbol} ×
                      </Badge>
                    ))}
                  </HStack>
                )}
                {pendingRemoves.length > 0 && (
                  <HStack gap={1} flexWrap="wrap" pl={6} mt={2}>
                    <Text fontSize="xs" color="fg.error">Removing:</Text>
                    {pendingRemoves.map(id => {
                      const p = currentMembers.find(m => m.id === id);
                      return p ? (
                        <Badge
                          key={id}
                          size="sm"
                          variant="outline"
                          colorPalette="red"
                          fontFamily="mono"
                          cursor="pointer"
                          textDecoration="line-through"
                          onClick={() => onToggleRemove(id)}
                          title={`Undo remove ${p.symbol}`}
                        >
                          {p.symbol}
                        </Badge>
                      ) : null;
                    })}
                  </HStack>
                )}
              </Box>

              {/* Divider */}
              <Box borderTopWidth="1px" borderColor="border.subtle" />

              {/* Available positions to add */}
              <Box>
                <HStack mb={2} gap={2}>
                  <FiPlus color="var(--chakra-colors-blue-500)" />
                  <Text fontSize="sm" fontWeight="semibold">Add positions</Text>
                </HStack>
                <Box position="relative" mb={2} pl={6}>
                  <Box position="absolute" left={6} top="50%" transform="translateY(-50%)" color="fg.muted" pointerEvents="none" zIndex={1}>
                    <FiSearch size={14} />
                  </Box>
                  <Input
                    size="sm"
                    pl={8}
                    placeholder="Search by ticker..."
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                  />
                </Box>
                <Box maxH="200px" overflowY="auto" pl={6}>
                  {filteredAvailable.length === 0 ? (
                    <Text fontSize="sm" color="fg.muted">
                      {search ? 'No matching positions' : 'All positions are assigned to this category'}
                    </Text>
                  ) : (
                    <HStack gap={1} flexWrap="wrap">
                      {filteredAvailable.map(p => (
                        <Badge
                          key={p.id}
                          size="sm"
                          variant="outline"
                          colorPalette="gray"
                          fontFamily="mono"
                          cursor="pointer"
                          title={`Add ${p.symbol} to ${categoryName}`}
                          onClick={() => onToggleAdd(p.id)}
                          _hover={{ colorPalette: 'brand', borderColor: 'brand.400' }}
                        >
                          + {p.symbol}
                          {p.market_value != null && (
                            <Text as="span" ml={1} fontWeight="normal" opacity={0.7}>
                              {formatMoney(p.market_value, currency, { maximumFractionDigits: 0, notation: 'compact' })}
                            </Text>
                          )}
                        </Badge>
                      ))}
                    </HStack>
                  )}
                </Box>
              </Box>
            </VStack>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              colorPalette="brand"
              onClick={onSave}
              disabled={changeCount === 0 || isSaving}
            >
              {isSaving ? 'Saving...' : changeCount === 0 ? 'No changes' : `Save ${changeCount} change${changeCount !== 1 ? 's' : ''}`}
            </Button>
          </DialogFooter>
          <DialogCloseTrigger />
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
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
    background: isDragging ? 'var(--chakra-colors-bg-subtle)' : undefined,
  };
  const target = Number(cat.target_allocation_pct ?? 0);
  const actual = Number(cat.actual_allocation_pct ?? 0);
  const drift = actual - target;

  return (
    <Table.Row ref={setNodeRef} style={style}>
      <Table.Cell width="40px" px={2}>
        <Box
          {...attributes}
          {...listeners}
          cursor="grab"
          _active={{ cursor: 'grabbing' }}
          color="fg.muted"
          _hover={{ color: 'fg.default' }}
          display="flex"
          alignItems="center"
        >
          <RiDraggable size={18} />
        </Box>
      </Table.Cell>
      <Table.Cell><Text fontWeight="semibold">{cat.name}</Text></Table.Cell>
      <Table.Cell textAlign="right">{target}%</Table.Cell>
      <Table.Cell textAlign="right">{actual.toFixed(1)}%</Table.Cell>
      <Table.Cell textAlign="right">
        <Text color={Math.abs(drift) > 5 ? 'status.danger' : drift !== 0 ? 'status.warning' : 'fg.muted'}>
          {drift > 0 ? '+' : ''}{drift.toFixed(1)}%
        </Text>
      </Table.Cell>
      <Table.Cell textAlign="right">{cat.positions_count ?? 0}</Table.Cell>
      <Table.Cell textAlign="right">{formatMoney(cat.total_value ?? 0, currency, { maximumFractionDigits: 0 })}</Table.Cell>
      <Table.Cell>
        <HStack gap={1}>
          <Button size="xs" variant="outline" onClick={() => onEdit(cat)}>Edit</Button>
          <Button size="xs" variant="outline" onClick={() => onAssign(cat)}>Assign</Button>
        </HStack>
      </Table.Cell>
    </Table.Row>
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

const PortfolioCategories: React.FC = () => {
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

  const { data: viewsData } = useCategoryViews();
  const availableViews = viewsData ?? [{ key: 'custom', label: 'Personalized' }];

  const { data: categoriesData, isLoading } = useCategories(activeView);
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

  const createMutation = useMutation(
    () => {
      const target = newTargetPct ? parseFloat(newTargetPct) : undefined;
      return portfolioApi.createCategory({
        name: newName.trim(),
        target_allocation_pct: target,
        category_type: activeView,
      });
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        queryClient.invalidateQueries('portfolioCategoryViews');
        toast.success('Category created');
        setNewName('');
        setNewTargetPct('');
        setCreateOpen(false);
      },
      onError: (err) => { toast.error(`Failed to create category: ${handleApiError(err)}`); },
    },
  );

  const updateMutation = useMutation(
    () => {
      if (!selectedCategory) throw new Error('No category selected');
      const target = newTargetPct ? parseFloat(newTargetPct) : undefined;
      return portfolioApi.updateCategory(selectedCategory.id, { name: newName.trim(), target_allocation_pct: target });
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        toast.success('Category updated');
        setEditOpen(false);
        setSelectedCategory(null);
      },
      onError: (err) => { toast.error(`Failed to update category: ${handleApiError(err)}`); },
    },
  );

  const assignMutation = useMutation(
    async () => {
      if (!selectedCategory) throw new Error('No category selected');
      const catId = selectedCategory.id;
      for (const posId of pendingRemoves) {
        await portfolioApi.unassignPosition(catId, posId);
      }
      if (pendingAdds.length > 0) {
        await portfolioApi.assignPositions(catId, pendingAdds);
      }
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        if (selectedCategory) queryClient.invalidateQueries(['categoryPositions', selectedCategory.id]);
        const total = pendingAdds.length + pendingRemoves.length;
        toast.success(`Updated ${total} position(s)`);
        setAssignOpen(false);
        setSelectedCategory(null);
      },
      onError: (err) => { toast.error(`Failed to update positions: ${handleApiError(err)}`); },
    },
  );

  const applyPresetMutation = useMutation(
    (presetId: string) => api.post('/portfolio/categories/apply-preset', { preset: presetId }),
    {
      onSuccess: (_data, presetId) => {
        queryClient.invalidateQueries('portfolioCategories');
        queryClient.invalidateQueries('portfolioCategoryViews');
        setActiveView(presetId);
        toast.success(`Switched to ${VIEW_LABELS[presetId] ?? presetId} view`);
        setPresetOpen(false);
      },
      onError: (err) => { toast.error(`Failed to apply preset: ${handleApiError(err)}`); },
    },
  );

  // Auto-apply preset when switching to a non-custom tab with no (or empty) categories
  useEffect(() => {
    if (activeView === 'custom') return;
    if (isLoading) return;
    if (appliedPresetsRef.current.has(activeView)) return;
    const cats = (categoriesData?.categories ?? []) as CategoryRow[];
    const totalAssigned = cats.reduce((s, c) => s + (c.positions_count ?? 0), 0);
    if (cats.length === 0 || totalAssigned === 0) {
      appliedPresetsRef.current.add(activeView);
      applyPresetMutation.mutate(activeView);
    }
  }, [activeView, isLoading, categoriesData]);

  const moveMutation = useMutation(
    async (args: { positionId: number; fromCategoryId: number; toCategoryId: number }) => {
      await api.delete(`/portfolio/categories/${args.fromCategoryId}/positions/${args.positionId}`);
      await api.post(`/portfolio/categories/${args.toCategoryId}/positions`, {
        position_ids: [args.positionId],
      });
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        queryClient.invalidateQueries('categoryPositions');
        toast.success('Position moved');
      },
      onError: (err) => { toast.error(`Failed to move: ${handleApiError(err)}`); },
    },
  );

  const reorderMutation = useMutation(
    (orderedIds: number[]) => portfolioApi.reorderCategories(orderedIds),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
      },
      onError: (err) => { toast.error(`Failed to reorder: ${handleApiError(err)}`); },
    },
  );

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
    <Box p={4}>
      <Stack gap={4}>
        <PageHeader
          title="Categories"
          subtitle="Target allocations and position assignment"
          rightContent={
            <HStack gap={2}>
              <Button size="sm" variant="outline" onClick={() => setPresetOpen(true)}>
                <Icon mr={1}><FiZap /></Icon> Auto-Categorize
              </Button>

              <HStack gap={1}>
                <Button
                  size="xs"
                  variant={view === 'card' ? 'solid' : 'ghost'}
                  onClick={() => setView('card')}
                  aria-label="Card view"
                >
                  <FiGrid />
                </Button>
                <Button
                  size="xs"
                  variant={view === 'table' ? 'solid' : 'ghost'}
                  onClick={() => setView('table')}
                  aria-label="Table view"
                >
                  <FiList />
                </Button>
              </HStack>

              <Button colorPalette="brand" onClick={() => { setNewName(''); setNewTargetPct(''); setCreateOpen(true); }}>
                + New Category
              </Button>
            </HStack>
          }
        />

        {/* Fixed category tabs */}
        <HStack
          gap={0}
          borderWidth="1px"
          borderColor="border.subtle"
          borderRadius="lg"
          overflow="hidden"
          flexWrap="wrap"
          bg="bg.subtle"
          p={1}
        >
          {FIXED_TABS.map((tab) => (
            <Button
              key={tab.key}
              size="sm"
              variant={activeView === tab.key ? 'solid' : 'ghost'}
              colorPalette={activeView === tab.key ? 'brand' : undefined}
              onClick={() => { setActiveView(tab.key); setDetailCatId(null); }}
              borderRadius="md"
              fontWeight={activeView === tab.key ? 'semibold' : 'normal'}
              minW="auto"
              px={4}
            >
              {tab.label}
            </Button>
          ))}
        </HStack>

        {categories.length > 0 && <AllocationChart categories={categories} currency={currency} />}

        {isLoading || (activeView !== 'custom' && applyPresetMutation.isLoading) ? (
          <TableSkeleton rows={5} cols={4} />
        ) : categories.length === 0 ? (
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardBody>
              <VStack gap={2} py={4}>
                <Text color="fg.muted">
                  {activeView === 'custom'
                    ? 'No categories yet. Create one to group positions and track target allocation.'
                    : `No categories in this view. Use Auto-Categorize to create "${VIEW_LABELS[activeView] ?? activeView}" categories.`}
                </Text>
                {activeView !== 'custom' && (
                  <Button size="sm" variant="outline" onClick={() => applyPresetMutation.mutate(activeView)}>
                    <Icon mr={1}><FiZap /></Icon> Auto-Categorize
                  </Button>
                )}
              </VStack>
            </CardBody>
          </CardRoot>
        ) : view === 'table' ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleTableDragEnd}
          >
            <SortableContext items={tableSortableIds} strategy={verticalListSortingStrategy}>
              <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl" overflow="hidden">
                <Table.Root size="sm">
                  <Table.Header>
                    <Table.Row>
                      <Table.ColumnHeader width="40px" px={2} />
                      <Table.ColumnHeader>Category</Table.ColumnHeader>
                      <Table.ColumnHeader textAlign="right">Target %</Table.ColumnHeader>
                      <Table.ColumnHeader textAlign="right">Actual %</Table.ColumnHeader>
                      <Table.ColumnHeader textAlign="right">Drift</Table.ColumnHeader>
                      <Table.ColumnHeader textAlign="right">Positions</Table.ColumnHeader>
                      <Table.ColumnHeader textAlign="right">Value</Table.ColumnHeader>
                      <Table.ColumnHeader />
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>
                    {categories.map((cat) => (
                      <SortableTableRow
                        key={cat.id}
                        cat={cat}
                        currency={currency}
                        onEdit={openEdit}
                        onAssign={openAssign}
                      />
                    ))}
                  </Table.Body>
                </Table.Root>
              </CardRoot>
            </SortableContext>
          </DndContext>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
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
                    onToggleDetail={() => setDetailCatId(prev => prev === cat.id ? null : cat.id)}
                  />
                </DroppableCategory>
              ))}
            </SimpleGrid>
            <DragOverlay>
              {activeDrag ? (
                <Badge size="sm" variant="solid" colorPalette="brand" fontFamily="mono">
                  {activeDrag.symbol}
                </Badge>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}

        {/* Uncategorized bucket */}
        {uncategorized.positions_count > 0 && (
          <CardRoot
            bg="bg.card"
            borderWidth="1px"
            borderColor="border.subtle"
            borderRadius="xl"
            borderStyle="dashed"
          >
            <CardBody>
              <HStack justify="space-between" align="center" mb={2}>
                <HStack gap={2}>
                  <Badge colorPalette="gray" variant="subtle" size="sm">Uncategorized</Badge>
                  <Text fontWeight="semibold" color="fg.muted">
                    {uncategorized.positions_count} position{uncategorized.positions_count !== 1 ? 's' : ''} not in any {VIEW_LABELS[activeView] ?? activeView} category
                  </Text>
                </HStack>
                <Text fontSize="sm" fontFamily="mono" color="fg.muted">
                  {formatMoney(uncategorized.total_value, currency, { maximumFractionDigits: 0 })}
                  {' · '}
                  {uncategorized.actual_allocation_pct.toFixed(1)}%
                </Text>
              </HStack>
              <HStack gap={1} flexWrap="wrap">
                {allPositions
                  .filter(p => uncategorized.position_ids?.includes(p.id))
                  .slice(0, 20)
                  .map(p => (
                    <Badge
                      key={p.id}
                      size="sm"
                      variant="outline"
                      colorPalette="gray"
                      fontFamily="mono"
                    >
                      {p.symbol}
                    </Badge>
                  ))}
                {uncategorized.positions_count > 20 && (
                  <Badge size="sm" variant="subtle" colorPalette="gray">
                    +{uncategorized.positions_count - 20} more
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mt={2}>
                Assign these positions to categories above using "Manage Positions", or drag them in card view.
              </Text>
            </CardBody>
          </CardRoot>
        )}

        {suggestions.length > 0 && (
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardHeader pb={2}>
              <HStack gap={2}>
                <Text fontWeight="bold">Rebalancing Preview</Text>
                <Badge colorPalette="orange">{suggestions.length} adjustments</Badge>
              </HStack>
            </CardHeader>
            <CardBody pt={2}>
              <HStack gap={6} align="start" flexWrap="wrap" mb={4}>
                <VStack align="center" gap={1}>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted">CURRENT</Text>
                  <Box w="120px" h="120px">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={categories.filter(c => (c.actual_allocation_pct ?? 0) > 0).map(c => ({ name: c.name, value: Number(c.actual_allocation_pct ?? 0) }))}
                          dataKey="value"
                          innerRadius={30}
                          outerRadius={50}
                          paddingAngle={2}
                        >
                          {categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </Box>
                </VStack>
                <VStack align="center" gap={1}>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted">TARGET</Text>
                  <Box w="120px" h="120px">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={categories.filter(c => (c.target_allocation_pct ?? 0) > 0).map(c => ({ name: c.name, value: Number(c.target_allocation_pct ?? 0) }))}
                          dataKey="value"
                          innerRadius={30}
                          outerRadius={50}
                          paddingAngle={2}
                        >
                          {categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </Box>
                </VStack>
              </HStack>
              <VStack align="stretch" gap={3}>
                {suggestions.map((s: any, i: number) => (
                  <Box key={i} p={3} borderWidth="1px" borderColor="border.subtle" borderRadius="lg">
                    <HStack justify="space-between" mb={1}>
                      <HStack gap={2}>
                        <Text fontWeight="semibold">{s.category}</Text>
                        <Badge colorPalette={s.direction === 'BUY' ? 'green' : 'red'} size="sm">{s.direction}</Badge>
                      </HStack>
                      <Text fontSize="sm" fontWeight="bold">{formatMoney(s.amount, currency, { maximumFractionDigits: 0 })}</Text>
                    </HStack>
                    <HStack gap={3} fontSize="xs" color="fg.muted">
                      <Text>Target: {s.target_pct}%</Text>
                      <Text>Actual: {s.actual_pct}%</Text>
                      <Text color={Math.abs(s.drift_pct) > 5 ? 'fg.error' : 'fg.muted'}>Drift: {s.drift_pct > 0 ? '+' : ''}{s.drift_pct}%</Text>
                    </HStack>
                    {s.positions?.length > 0 && (
                      <Box mt={2}>
                        {s.positions.map((p: any, j: number) => (
                          <HStack key={j} justify="space-between" fontSize="xs" py={0.5}>
                            <Text fontFamily="mono">{p.symbol}</Text>
                            <Text>{p.shares > 0 ? `~${p.shares} sh` : ''} · {formatMoney(p.est_value, currency, { maximumFractionDigits: 0 })}</Text>
                          </HStack>
                        ))}
                      </Box>
                    )}
                  </Box>
                ))}
              </VStack>
            </CardBody>
          </CardRoot>
        )}
      </Stack>

      {/* Create category dialog */}
      <DialogRoot open={createOpen} onOpenChange={(e) => setCreateOpen(e.open)}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent>
            <DialogHeader>New Category</DialogHeader>
            <DialogBody>
              <VStack gap={3} align="stretch">
                <Field.Root>
                  <Field.Label>Name</Field.Label>
                  <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Growth" />
                </Field.Root>
                <Field.Root>
                  <Field.Label>Target allocation %</Field.Label>
                  <Input type="number" value={newTargetPct} onChange={(e) => setNewTargetPct(e.target.value)} placeholder="e.g. 40" />
                </Field.Root>
              </VStack>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button colorPalette="brand" onClick={handleCreate} disabled={!newName.trim() || createMutation.isLoading}>Create</Button>
            </DialogFooter>
            <DialogCloseTrigger />
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>

      {/* Edit category dialog */}
      <DialogRoot open={editOpen} onOpenChange={(e) => { if (!e.open) setEditOpen(false); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent>
            <DialogHeader>Edit Category</DialogHeader>
            <DialogBody>
              <VStack gap={3} align="stretch">
                <Field.Root>
                  <Field.Label>Name</Field.Label>
                  <Input value={newName} onChange={(e) => setNewName(e.target.value)} />
                </Field.Root>
                <Field.Root>
                  <Field.Label>Target allocation %</Field.Label>
                  <Input type="number" value={newTargetPct} onChange={(e) => setNewTargetPct(e.target.value)} />
                </Field.Root>
              </VStack>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button colorPalette="brand" onClick={handleUpdate} disabled={!newName.trim() || updateMutation.isLoading}>Save</Button>
            </DialogFooter>
            <DialogCloseTrigger />
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>

      {/* Manage positions dialog -- two-section layout */}
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
        onToggleAdd={(id) => setPendingAdds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
        onToggleRemove={(id) => setPendingRemoves(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
        search={assignSearch}
        onSearchChange={setAssignSearch}
        onSave={handleSaveAssignments}
        isSaving={assignMutation.isLoading}
        changeCount={pendingAdds.length + pendingRemoves.length}
      />

      {/* Auto-categorize presets dialog */}
      <DialogRoot open={presetOpen} onOpenChange={(e) => setPresetOpen(e.open)}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="lg">
            <DialogHeader>Auto-Categorize Positions</DialogHeader>
            <DialogBody>
              <Text fontSize="sm" color="fg.muted" mb={4}>
                Choose a preset to automatically create categories and assign positions.
                Existing categories will not be removed.
              </Text>
              <SimpleGrid columns={{ base: 1, md: 2 }} gap={3}>
                {PRESETS.map((preset) => (
                  <Box
                    key={preset.id}
                    p={4}
                    borderWidth="1px"
                    borderColor="border.subtle"
                    borderRadius="lg"
                    cursor="pointer"
                    _hover={{ borderColor: 'brand.500', bg: 'bg.subtle' }}
                    onClick={() => applyPresetMutation.mutate(preset.id)}
                    opacity={applyPresetMutation.isLoading ? 0.5 : 1}
                    pointerEvents={applyPresetMutation.isLoading ? 'none' : 'auto'}
                  >
                    <Text fontWeight="semibold" mb={1}>{preset.label}</Text>
                    <Text fontSize="xs" color="fg.muted">{preset.description}</Text>
                  </Box>
                ))}
              </SimpleGrid>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPresetOpen(false)}>Cancel</Button>
            </DialogFooter>
            <DialogCloseTrigger />
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default PortfolioCategories;
