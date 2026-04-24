import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ClipboardList } from 'lucide-react';
import toast from 'react-hot-toast';

import api from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import {
  ResponsiveModal as Dialog,
  ResponsiveModalContent as DialogContent,
  ResponsiveModalFooter as DialogFooter,
  ResponsiveModalHeader as DialogHeader,
  ResponsiveModalTitle as DialogTitle,
} from '@/components/ui/responsive-modal';
import EmptyState from '@/components/ui/EmptyState';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { actionChipClass } from '@/lib/picks';
import { cn } from '@/lib/utils';

type QueueStateTab = 'DRAFT' | 'APPROVED' | 'PUBLISHED' | 'REJECTED';

interface CandidateRow {
  id: number;
  ticker: string;
  action: string;
  state: QueueStateTab;
  confidence: number | null;
  thesis: string | null;
  target_price: string | null;
  stop_loss: string | null;
  generator_name: string;
  generator_version: string;
  generated_at: string | null;
  published_at: string | null;
  state_transitioned_at: string | null;
  state_transitioned_by: number | null;
  source_email_parse_id: number | null;
  email_subject?: string | null;
  email_sender?: string | null;
  parsed_at?: string | null;
}

interface QueueResponse {
  items: CandidateRow[];
  total: number;
  limit: number;
  offset: number;
}

interface CountsResponse {
  DRAFT: number;
  APPROVED: number;
  PUBLISHED: number;
  REJECTED: number;
}


const PicksValidator: React.FC = () => {
  const queryClient = useQueryClient();
  const [tab, setTab] = React.useState<QueueStateTab>('DRAFT');
  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectId, setRejectId] = React.useState<number | null>(null);
  const [rejectReason, setRejectReason] = React.useState('');
  const [editRow, setEditRow] = React.useState<CandidateRow | null>(null);
  const [viewRow, setViewRow] = React.useState<CandidateRow | null>(null);
  const [editForm, setEditForm] = React.useState({
    ticker: '',
    action: 'buy',
    target_price: '',
    stop_loss: '',
    thesis: '',
  });

  const countsQuery = useQuery({
    queryKey: ['admin-picks-counts'],
    queryFn: async () => {
      const res = await api.get<CountsResponse>('/admin/picks/queue/counts');
      return res.data;
    },
  });

  const queueQuery = useQuery({
    queryKey: ['admin-picks-queue', tab],
    queryFn: async () => {
      const res = await api.get<QueueResponse>(`/admin/picks/queue?state=${tab}&limit=50`);
      return res.data;
    },
  });

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-picks-counts'] });
    await queryClient.invalidateQueries({ queryKey: ['admin-picks-queue'] });
  };

  const approveMut = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/admin/picks/${id}/approve`);
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['admin-picks-queue', tab] });
      const prev = queryClient.getQueryData<QueueResponse>(['admin-picks-queue', tab]);
      const prevCounts = queryClient.getQueryData<CountsResponse>(['admin-picks-counts']);
      if (prev) {
        queryClient.setQueryData(['admin-picks-queue', tab], {
          ...prev,
          items: prev.items.filter((c) => c.id !== id),
          total: Math.max(0, prev.total - 1),
        });
      }
      if (prevCounts) {
        queryClient.setQueryData(['admin-picks-counts'], {
          ...prevCounts,
          DRAFT: Math.max(0, prevCounts.DRAFT - 1),
          APPROVED: prevCounts.APPROVED + 1,
        });
      }
      return { prev, prevCounts };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(['admin-picks-queue', tab], ctx.prev);
      if (ctx?.prevCounts) queryClient.setQueryData(['admin-picks-counts'], ctx.prevCounts);
      toast.error('Approve failed');
    },
    onSettled: () => {
      void invalidateAll();
    },
  });

  const publishMut = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/admin/picks/${id}/publish`);
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['admin-picks-queue', tab] });
      const prev = queryClient.getQueryData<QueueResponse>(['admin-picks-queue', tab]);
      const prevCounts = queryClient.getQueryData<CountsResponse>(['admin-picks-counts']);
      if (prev) {
        queryClient.setQueryData(['admin-picks-queue', tab], {
          ...prev,
          items: prev.items.filter((c) => c.id !== id),
          total: Math.max(0, prev.total - 1),
        });
      }
      if (prevCounts) {
        queryClient.setQueryData(['admin-picks-counts'], {
          ...prevCounts,
          APPROVED: Math.max(0, prevCounts.APPROVED - 1),
          PUBLISHED: prevCounts.PUBLISHED + 1,
        });
      }
      return { prev, prevCounts };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(['admin-picks-queue', tab], ctx.prev);
      if (ctx?.prevCounts) queryClient.setQueryData(['admin-picks-counts'], ctx.prevCounts);
      toast.error('Publish failed');
    },
    onSettled: () => {
      void invalidateAll();
    },
  });

  const rejectMut = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) => {
      await api.post(`/admin/picks/${id}/reject`, { reason });
    },
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: ['admin-picks-queue', tab] });
      const prev = queryClient.getQueryData<QueueResponse>(['admin-picks-queue', tab]);
      const prevCounts = queryClient.getQueryData<CountsResponse>(['admin-picks-counts']);
      if (prev) {
        queryClient.setQueryData(['admin-picks-queue', tab], {
          ...prev,
          items: prev.items.filter((c) => c.id !== id),
          total: Math.max(0, prev.total - 1),
        });
      }
      if (prevCounts) {
        const fromDraft = tab === 'DRAFT';
        const fromApproved = tab === 'APPROVED';
        queryClient.setQueryData(['admin-picks-counts'], {
          ...prevCounts,
          DRAFT: fromDraft ? Math.max(0, prevCounts.DRAFT - 1) : prevCounts.DRAFT,
          APPROVED: fromApproved ? Math.max(0, prevCounts.APPROVED - 1) : prevCounts.APPROVED,
          REJECTED: prevCounts.REJECTED + 1,
        });
      }
      return { prev, prevCounts };
    },
    onError: (_e, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(['admin-picks-queue', tab], ctx.prev);
      if (ctx?.prevCounts) queryClient.setQueryData(['admin-picks-counts'], ctx.prevCounts);
      toast.error('Reject failed');
    },
    onSettled: () => {
      void invalidateAll();
    },
  });

  const patchMut = useMutation({
    mutationFn: async (payload: { id: number; body: Record<string, unknown> }) => {
      const res = await api.patch<CandidateRow>(`/admin/picks/${payload.id}`, payload.body);
      return res.data;
    },
    onSuccess: () => {
      toast.success('Saved');
      setEditRow(null);
      void invalidateAll();
    },
    onError: () => {
      toast.error('Save failed');
    },
  });

  const detailQuery = useQuery({
    queryKey: ['admin-picks-detail', viewRow?.id],
    enabled: Boolean(viewRow),
    queryFn: async () => {
      const res = await api.get<CandidateRow>(`/admin/picks/${viewRow!.id}`);
      return res.data;
    },
  });

  const openReject = (id: number) => {
    setRejectId(id);
    setRejectReason('');
    setRejectOpen(true);
  };

  const submitReject = () => {
    if (rejectId == null) return;
    rejectMut.mutate(
      { id: rejectId, reason: rejectReason },
      {
        onSuccess: () => {
          setRejectOpen(false);
          setRejectId(null);
        },
      },
    );
  };

  const openEdit = (row: CandidateRow) => {
    setEditRow(row);
    setEditForm({
      ticker: row.ticker,
      action: row.action.toLowerCase(),
      target_price: row.target_price ?? '',
      stop_loss: row.stop_loss ?? '',
      thesis: row.thesis ?? '',
    });
  };

  const submitEdit = () => {
    if (!editRow) return;
    patchMut.mutate({
      id: editRow.id,
      body: {
        ticker: editForm.ticker,
        action: editForm.action,
        target_price: editForm.target_price || null,
        stop_loss: editForm.stop_loss || null,
        thesis: editForm.thesis,
      },
    });
  };

  const counts = countsQuery.data;
  const loading = queueQuery.isLoading || countsQuery.isLoading;
  const err = queueQuery.isError || countsQuery.isError;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4">
      <div>
        <h1 className="font-heading text-xl font-semibold tracking-tight">Picks validator</h1>
        <p className="text-sm text-muted-foreground">Review queue states, edit drafts, approve, publish, or reject.</p>
      </div>

      {err ? (
        <Card>
          <CardContent className="py-6 text-sm text-destructive">Failed to load queue. Retry from System Status.</CardContent>
        </Card>
      ) : null}

      <Tabs value={tab} onValueChange={(v) => setTab(v as QueueStateTab)}>
        <TabsList className="flex flex-wrap gap-1">
          {(['DRAFT', 'APPROVED', 'PUBLISHED', 'REJECTED'] as const).map((s) => (
            <TabsTrigger key={s} value={s} className="gap-1">
              {s === 'DRAFT' ? 'Draft' : s === 'APPROVED' ? 'Approved' : s === 'PUBLISHED' ? 'Published' : 'Rejected'}
              <Badge variant="secondary" className="ml-1 rounded-sm px-1.5 py-0 text-[10px]">
                {loading
                  ? '—'
                  : typeof counts === 'object' && counts != null && typeof counts[s] === 'number'
                    ? counts[s]
                    : '—'}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>

        {(['DRAFT', 'APPROVED', 'PUBLISHED', 'REJECTED'] as const).map((s) => (
          <TabsContent key={s} value={s} className="mt-4 space-y-3">
            {queueQuery.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : queueQuery.data?.items.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="Nothing in this queue"
                description="Candidates appear here when ingested or generated."
              />
            ) : (
              queueQuery.data?.items.map((row) => (
                <Card key={row.id}>
                  <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 pb-2">
                    <div>
                      <p className="font-mono text-2xl font-semibold tracking-tight">{row.ticker}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>{row.generator_name}</span>
                        <span>·</span>
                        <span>{row.generator_version}</span>
                        {row.generated_at ? <span>· generated {new Date(row.generated_at).toLocaleString()}</span> : null}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className={cn('font-medium uppercase', actionChipClass(row.action))}>{row.action}</Badge>
                      {row.confidence != null ? (
                        <Badge variant="outline">Score {row.confidence.toFixed(2)}</Badge>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{row.thesis || '_No thesis_'}</ReactMarkdown>
                    </div>
                    <div className="flex flex-wrap gap-4 text-muted-foreground">
                      {row.target_price ? <span>Target {row.target_price}</span> : null}
                      {row.stop_loss ? <span>Stop {row.stop_loss}</span> : null}
                    </div>
                  </CardContent>
                  <CardFooter className="flex flex-wrap gap-2 border-t border-border pt-3">
                    {tab === 'DRAFT' ? (
                      <>
                        <Button type="button" size="sm" onClick={() => approveMut.mutate(row.id)} disabled={approveMut.isPending}>
                          Approve
                        </Button>
                        <Button type="button" size="sm" variant="secondary" onClick={() => openReject(row.id)}>
                          Reject
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => openEdit(row)}>
                          Edit
                        </Button>
                      </>
                    ) : null}
                    {tab === 'APPROVED' ? (
                      <>
                        <Button type="button" size="sm" onClick={() => publishMut.mutate(row.id)} disabled={publishMut.isPending}>
                          Publish
                        </Button>
                        <Button type="button" size="sm" variant="secondary" onClick={() => openReject(row.id)}>
                          Reject
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setViewRow(row)}>
                          View
                        </Button>
                      </>
                    ) : null}
                    {(tab === 'PUBLISHED' || tab === 'REJECTED') && (
                      <Button type="button" size="sm" variant="ghost" onClick={() => setViewRow(row)}>
                        View
                      </Button>
                    )}
                  </CardFooter>
                </Card>
              ))
            )}
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject candidate</DialogTitle>
          </DialogHeader>
          <Textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason (shown in audit log)"
            className="min-h-24"
          />
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setRejectOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={submitReject} disabled={rejectMut.isPending}>
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(editRow)} onOpenChange={(o) => !o && setEditRow(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit draft</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label htmlFor="ticker">Ticker</Label>
              <Input
                id="ticker"
                value={editForm.ticker}
                onChange={(e) => setEditForm((f) => ({ ...f, ticker: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="action">Action</Label>
              <Input
                id="action"
                value={editForm.action}
                onChange={(e) => setEditForm((f) => ({ ...f, action: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="tp">Target price</Label>
              <Input
                id="tp"
                value={editForm.target_price}
                onChange={(e) => setEditForm((f) => ({ ...f, target_price: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="sl">Stop loss</Label>
              <Input
                id="sl"
                value={editForm.stop_loss}
                onChange={(e) => setEditForm((f) => ({ ...f, stop_loss: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="thesis">Thesis</Label>
              <Textarea
                id="thesis"
                className="min-h-28"
                value={editForm.thesis}
                onChange={(e) => setEditForm((f) => ({ ...f, thesis: e.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setEditRow(null)}>
              Cancel
            </Button>
            <Button type="button" onClick={submitEdit} disabled={patchMut.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(viewRow)} onOpenChange={(o) => !o && setViewRow(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Candidate detail</DialogTitle>
          </DialogHeader>
          {detailQuery.isLoading ? <Skeleton className="h-40 w-full" /> : null}
          {detailQuery.data ? (
            <div className="space-y-2 text-sm">
              <p className="font-mono text-lg font-semibold">{detailQuery.data.ticker}</p>
              {detailQuery.data.email_subject ? (
                <p>
                  <span className="text-muted-foreground">Email:</span> {detailQuery.data.email_subject}
                </p>
              ) : null}
              {detailQuery.data.email_sender ? (
                <p>
                  <span className="text-muted-foreground">From:</span> {detailQuery.data.email_sender}
                </p>
              ) : null}
              {detailQuery.data.parsed_at ? (
                <p>
                  <span className="text-muted-foreground">Parsed:</span>{' '}
                  {new Date(detailQuery.data.parsed_at).toLocaleString()}
                </p>
              ) : null}
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{detailQuery.data.thesis || ''}</ReactMarkdown>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PicksValidator;
