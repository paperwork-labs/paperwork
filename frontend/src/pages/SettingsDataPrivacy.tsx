/**
 * Settings -> Data Privacy.
 *
 * Two-card layout:
 *  - Export your data: kicks off a GDPR data export job, polls until
 *    completed/failed, surfaces a download link.
 *  - Delete your account: two-phase delete. We display the
 *    confirmation token exactly once and require the user to retype
 *    "DELETE MY ACCOUNT" before sending it.
 *
 * Loading / error / empty / data states are tracked explicitly per
 * the no-silent-fallback rule (no `?? 0` on totals).
 */

import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import hotToast from 'react-hot-toast';
import { Loader2, Download, AlertTriangle, Copy } from 'lucide-react';

import { PageHeader } from '../components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

import {
  dataPrivacyApi,
  type DeleteJob,
  type ExportJob,
} from '../services/dataPrivacy';

const POLL_INTERVAL_MS = 4000;
const TERMINAL_STATUSES: ReadonlyArray<ExportJob['status']> = [
  'completed',
  'failed',
  'expired',
];
const DELETE_PHRASE = 'DELETE MY ACCOUNT';

function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function ExportCard() {
  const queryClient = useQueryClient();
  const [activeJobId, setActiveJobId] = React.useState<number | null>(null);

  const startMutation = useMutation({
    mutationFn: () => dataPrivacyApi.startExport(),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      queryClient.setQueryData(['gdprExportJob', job.id], job);
      hotToast.success('Data export queued');
    },
    onError: () => hotToast.error('Failed to queue data export'),
  });

  const jobQuery = useQuery<ExportJob>({
    queryKey: ['gdprExportJob', activeJobId],
    queryFn: () => dataPrivacyApi.getExportJob(activeJobId as number),
    enabled: activeJobId !== null,
    refetchInterval: (query) => {
      const data = query.state.data as ExportJob | undefined;
      if (!data) return POLL_INTERVAL_MS;
      return TERMINAL_STATUSES.includes(data.status) ? false : POLL_INTERVAL_MS;
    },
  });

  const job = jobQuery.data;
  const downloadUrl = job ? dataPrivacyApi.resolveDownloadUrl(job) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export your data</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Build a ZIP containing every row in AxiomFolio that belongs to your
          account. Includes positions, orders, watchlists, narratives, and
          settings, one CSV per table plus a manifest.
        </p>

        <Button
          type="button"
          onClick={() => startMutation.mutate()}
          disabled={startMutation.isPending}
        >
          {startMutation.isPending ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" /> Queuing…
            </>
          ) : (
            'Request a new export'
          )}
        </Button>

        {activeJobId !== null && (
          <div className="rounded-md border p-3 text-sm">
            {jobQuery.isLoading && !job ? (
              <p className="text-muted-foreground">Loading job…</p>
            ) : jobQuery.isError ? (
              <p className="text-destructive">
                Couldn't read job status. Try again in a moment.
              </p>
            ) : job ? (
              <div className="space-y-2">
                <p>
                  Status:{' '}
                  <span className="font-mono text-foreground">{job.status}</span>
                </p>
                <p className="text-muted-foreground">
                  Requested {new Date(job.requested_at).toLocaleString()}
                </p>
                {job.bytes_written !== null &&
                  job.bytes_written !== undefined && (
                    <p className="text-muted-foreground">
                      Size: {formatBytes(job.bytes_written)}
                    </p>
                  )}
                {job.status === 'completed' && downloadUrl && (
                  <Button asChild type="button" variant="outline">
                    <a href={downloadUrl} download>
                      <Download className="mr-2 size-4" />
                      Download ZIP
                    </a>
                  </Button>
                )}
                {job.status === 'failed' && job.error_message && (
                  <Alert variant="destructive">
                    <AlertTriangle className="size-4" />
                    <AlertTitle>Export failed</AlertTitle>
                    <AlertDescription className="font-mono text-xs">
                      {job.error_message}
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DeleteCard() {
  const queryClient = useQueryClient();
  const [activeJobId, setActiveJobId] = React.useState<number | null>(null);
  const [oneTimeToken, setOneTimeToken] = React.useState<string | null>(null);
  const [confirmationInput, setConfirmationInput] = React.useState('');
  const [tokenInput, setTokenInput] = React.useState('');

  const startMutation = useMutation({
    mutationFn: () => dataPrivacyApi.startDelete(),
    onSuccess: ({ job, confirmation_token }) => {
      setActiveJobId(job.id);
      setOneTimeToken(confirmation_token);
      setTokenInput('');
      queryClient.setQueryData(['gdprDeleteJob', job.id], job);
    },
    onError: () => hotToast.error('Failed to start account deletion'),
  });

  const confirmMutation = useMutation({
    mutationFn: () =>
      dataPrivacyApi.confirmDelete(activeJobId as number, tokenInput),
    onSuccess: (job) => {
      queryClient.setQueryData(['gdprDeleteJob', job.id], job);
      setOneTimeToken(null);
      hotToast.success('Account deletion confirmed; running…');
    },
    onError: () =>
      hotToast.error('Could not confirm deletion (check the token)'),
  });

  const jobQuery = useQuery<DeleteJob>({
    queryKey: ['gdprDeleteJob', activeJobId],
    queryFn: () => dataPrivacyApi.getDeleteJob(activeJobId as number),
    enabled: activeJobId !== null,
    refetchInterval: (query) => {
      const data = query.state.data as DeleteJob | undefined;
      if (!data) return POLL_INTERVAL_MS;
      return TERMINAL_STATUSES.includes(data.status) ? false : POLL_INTERVAL_MS;
    },
  });

  const phraseOk = confirmationInput === DELETE_PHRASE;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-destructive">Delete your account</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>This cannot be undone.</AlertTitle>
          <AlertDescription>
            We'll remove every row tied to your account: positions, orders,
            watchlists, settings, and broker connections. Audit-log rows are
            retained but anonymised. Make sure you've downloaded an export
            first.
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="delete-phrase">
            Type <span className="font-mono">{DELETE_PHRASE}</span> to enable
            deletion
          </Label>
          <Input
            id="delete-phrase"
            value={confirmationInput}
            onChange={(e) => setConfirmationInput(e.target.value)}
            placeholder={DELETE_PHRASE}
          />
        </div>

        <Button
          type="button"
          variant="destructive"
          onClick={() => startMutation.mutate()}
          disabled={!phraseOk || startMutation.isPending}
        >
          {startMutation.isPending ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" /> Requesting…
            </>
          ) : (
            'Begin deletion'
          )}
        </Button>

        {oneTimeToken && (
          <Alert>
            <AlertTitle>Save this confirmation token</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>
                Shown exactly once. Paste it below to confirm. Do not refresh
                this page until you've copied it.
              </p>
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={oneTimeToken}
                  className="font-mono text-xs"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  aria-label="Copy token"
                  onClick={() => {
                    void navigator.clipboard?.writeText(oneTimeToken);
                    hotToast.success('Token copied');
                  }}
                >
                  <Copy className="size-4" />
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {activeJobId !== null && (
          <div className="space-y-2">
            <Label htmlFor="delete-token">Confirmation token</Label>
            <Input
              id="delete-token"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="paste the token from above"
              className="font-mono text-xs"
            />
            <Button
              type="button"
              variant="destructive"
              onClick={() => confirmMutation.mutate()}
              disabled={!tokenInput || confirmMutation.isPending}
            >
              {confirmMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />{' '}
                  Confirming…
                </>
              ) : (
                'Confirm deletion'
              )}
            </Button>
          </div>
        )}

        {jobQuery.data && (
          <div className="rounded-md border p-3 text-sm">
            <p>
              Status:{' '}
              <span className="font-mono text-foreground">
                {jobQuery.data.status}
              </span>
            </p>
            <p className="text-muted-foreground">
              Requested{' '}
              {new Date(jobQuery.data.requested_at).toLocaleString()}
            </p>
            {jobQuery.data.error_message && (
              <p className="text-destructive font-mono text-xs">
                {jobQuery.data.error_message}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const SettingsDataPrivacy: React.FC = () => {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Data privacy"
        subtitle="Export everything we hold about your account, or delete the account entirely. GDPR / data-subject rights."
      />
      <div className="grid gap-6 md:grid-cols-2">
        <ExportCard />
        <DeleteCard />
      </div>
    </div>
  );
};

export default SettingsDataPrivacy;
