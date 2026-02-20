import React, { useState } from 'react';
import {
  Box,
  Text,
  Stack,
  HStack,
  Button,
  CardRoot,
  CardBody,
  VStack,
  SimpleGrid,
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
  Checkbox,
} from '@chakra-ui/react';
import PageHeader from '../../components/ui/PageHeader';
import { portfolioApi, handleApiError } from '../../services/api';
import { useQuery, useMutation, useQueryClient } from 'react-query';
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

const PortfolioCategories: React.FC = () => {
  const { currency } = useUserPreferences();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<CategoryRow | null>(null);
  const [newName, setNewName] = useState('');
  const [newTargetPct, setNewTargetPct] = useState<string>('');
  const [assignPositionIds, setAssignPositionIds] = useState<number[]>([]);

  const { data: categoriesData, isLoading } = useQuery(
    'portfolioCategories',
    () => portfolioApi.getCategories().then((r: any) => r?.data?.categories ?? [])
  );
  const categories = (categoriesData ?? []) as CategoryRow[];

  const { data: positionsData } = useQuery(
    'portfolioStocksForCategories',
    () => portfolioApi.getStocks(undefined, false).then((r: unknown) => (r as { data?: { data?: { stocks?: unknown[] }; stocks?: unknown[] }; stocks?: unknown[] })?.data?.data?.stocks ?? (r as { data?: { stocks?: unknown[] } })?.data?.stocks ?? [])
  );
  const allPositions = (positionsData ?? []) as Array<{ id: number; symbol: string; market_value?: number }>;

  const createMutation = useMutation(
    () => {
      const target = newTargetPct ? parseFloat(newTargetPct) : undefined;
      return portfolioApi.createCategory({ name: newName.trim(), target_allocation_pct: target });
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        toast.success('Category created');
        setNewName('');
        setNewTargetPct('');
        setCreateOpen(false);
      },
      onError: (err) => { toast.error(`Failed to create category: ${handleApiError(err)}`); },
    }
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
    }
  );

  const assignMutation = useMutation(
    () => {
      if (!selectedCategory || assignPositionIds.length === 0) throw new Error('No category or positions');
      return portfolioApi.assignPositions(selectedCategory.id, assignPositionIds);
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portfolioCategories');
        toast.success('Positions assigned');
        setAssignOpen(false);
        setSelectedCategory(null);
      },
      onError: (err) => { toast.error(`Failed to assign positions: ${handleApiError(err)}`); },
    }
  );

  const handleCreate = () => createMutation.mutate();
  const handleUpdate = () => updateMutation.mutate();
  const handleAssign = () => assignMutation.mutate();

  const openEdit = (cat: CategoryRow) => {
    setSelectedCategory(cat);
    setNewName(cat.name);
    setNewTargetPct(cat.target_allocation_pct != null ? String(cat.target_allocation_pct) : '');
    setEditOpen(true);
  };

  const openAssign = (cat: CategoryRow) => {
    setSelectedCategory(cat);
    setAssignPositionIds([]);
    setAssignOpen(true);
  };

  return (
    <Box p={4}>
      <Stack gap={4}>
        <PageHeader
          title="Categories"
          subtitle="Target allocations and position assignment"
          rightContent={
            <Button colorPalette="brand" onClick={() => { setNewName(''); setNewTargetPct(''); setCreateOpen(true); }}>
              + New Category
            </Button>
          }
        />

        {isLoading ? (
          <TableSkeleton rows={5} cols={4} />
        ) : categories.length === 0 ? (
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardBody>
              <Text color="fg.muted">No categories yet. Create one to group positions and track target allocation.</Text>
            </CardBody>
          </CardRoot>
        ) : (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
            {categories.map((cat) => {
              const target = cat.target_allocation_pct ?? 0;
              const actual = cat.actual_allocation_pct ?? 0;
              const diff = actual - target;
              return (
                <CardRoot key={cat.id} bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
                  <CardBody>
                    <Text fontWeight="semibold" mb={2}>{cat.name}</Text>
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
                      <Text fontSize="xs" color="fg.muted" mt={1}>{formatMoney(cat.total_value, currency, { maximumFractionDigits: 0 })}</Text>
                    )}
                    <HStack mt={3} gap={2}>
                      <Button size="xs" variant="outline" onClick={() => openEdit(cat)}>Edit</Button>
                      <Button size="xs" variant="outline" onClick={() => openAssign(cat)}>Manage Positions</Button>
                    </HStack>
                  </CardBody>
                </CardRoot>
              );
            })}
          </SimpleGrid>
        )}
      </Stack>

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

      <DialogRoot open={assignOpen} onOpenChange={(e) => { if (!e.open) setAssignOpen(false); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="md">
            <DialogHeader>Assign positions · {selectedCategory?.name}</DialogHeader>
            <DialogBody>
              <VStack align="stretch" gap={2} maxH="300px" overflowY="auto">
                {allPositions.map((p) => (
                  <Checkbox.Root
                    key={p.id}
                    checked={assignPositionIds.includes(p.id)}
                    onCheckedChange={(e) => {
                      setAssignPositionIds((prev) =>
                        e.checked ? [...prev, p.id] : prev.filter((id) => id !== p.id)
                      );
                    }}
                  >
                    <Checkbox.HiddenInput />
                    <Checkbox.Control />
                    <Checkbox.Label>
                      {p.symbol} {p.market_value != null ? ` · ${formatMoney(p.market_value, currency, { maximumFractionDigits: 0 })}` : ''}
                    </Checkbox.Label>
                  </Checkbox.Root>
                ))}
              </VStack>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAssignOpen(false)}>Cancel</Button>
              <Button colorPalette="brand" onClick={handleAssign} disabled={assignPositionIds.length === 0 || assignMutation.isLoading}>
                Add {assignPositionIds.length} position(s)
              </Button>
            </DialogFooter>
            <DialogCloseTrigger />
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default PortfolioCategories;
