import React from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import hotToast from 'react-hot-toast';

import { PageHeader } from '@/components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  accountRiskProfileApi,
  accountsApi,
  handleApiError,
  type RiskProfileLimits,
  type RiskProfileResponse,
} from '@/services/api';

const FIELD_LABELS: Record<keyof RiskProfileLimits, string> = {
  max_position_pct: 'Max single position',
  max_stage_2c_pct: 'Max Stage 2C concentration',
  max_options_pct: 'Max options exposure',
  max_daily_loss_pct: 'Max daily loss (halt)',
  hard_stop_pct: 'Hard-stop distance',
};

const FIELD_ORDER: (keyof RiskProfileLimits)[] = [
  'max_position_pct',
  'max_stage_2c_pct',
  'max_options_pct',
  'max_daily_loss_pct',
  'hard_stop_pct',
];

interface ManagedAccount {
  id: number;
  broker: string;
  account_number: string;
  account_name?: string | null;
  account_type: string;
}

function formatPct(value: string | null | undefined): string {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return `${(n * 100).toFixed(2)}%`;
}

function parseFraction(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) {
    throw new Error('must be a number');
  }
  if (n < 0 || n > 1) {
    throw new Error('must be between 0 and 1 (e.g. 0.05 for 5%)');
  }
  return trimmed;
}

const AccountRiskCard: React.FC<{ account: ManagedAccount }> = ({ account }) => {
  const queryClient = useQueryClient();
  const queryKey = ['account-risk-profile', account.id] as const;

  const query = useQuery<RiskProfileResponse>({
    queryKey,
    queryFn: () => accountRiskProfileApi.get(account.id),
  });

  const [draft, setDraft] = React.useState<
    Partial<Record<keyof RiskProfileLimits, string>>
  >({});
  const [fieldError, setFieldError] = React.useState<
    Partial<Record<keyof RiskProfileLimits, string>>
  >({});
  const [formError, setFormError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!query.data) return;
    const next: Partial<Record<keyof RiskProfileLimits, string>> = {};
    for (const field of FIELD_ORDER) {
      const v = query.data.per_account[field];
      next[field] = v == null ? '' : String(v);
    }
    setDraft(next);
    setFieldError({});
    setFormError(null);
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, string | null> = {};
      const nextErrors: Partial<Record<keyof RiskProfileLimits, string>> = {};
      for (const field of FIELD_ORDER) {
        try {
          payload[field] = parseFraction(draft[field] ?? '');
        } catch (err) {
          nextErrors[field] = (err as Error).message;
        }
      }
      if (Object.keys(nextErrors).length > 0) {
        setFieldError(nextErrors);
        throw new Error('fix field errors and try again');
      }
      setFieldError({});
      return accountRiskProfileApi.update(account.id, payload);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      setFormError(null);
      hotToast.success('Risk profile saved');
    },
    onError: (err) => {
      const msg = handleApiError(err);
      setFormError(msg);
      hotToast.error(msg);
    },
  });

  if (query.isLoading) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          Loading risk profile for {account.account_number}…
        </CardContent>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">
            Could not load risk profile for {account.account_number}.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => query.refetch()}
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const title = account.account_name
    ? `${account.account_name} (${account.account_number})`
    : `${account.broker.toUpperCase()} ${account.account_type} (${account.account_number})`;

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold">{title}</h3>
          <span className="text-xs text-muted-foreground">
            Effective = tighter of firm cap and your cap
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="py-2 pr-3">Limit</th>
                <th className="py-2 pr-3">Firm cap</th>
                <th className="py-2 pr-3">Your cap</th>
                <th className="py-2 pr-3">Effective</th>
              </tr>
            </thead>
            <tbody>
              {FIELD_ORDER.map((field) => {
                const err = fieldError[field];
                return (
                  <tr key={field} className="border-b border-border/60 align-top">
                    <td className="py-3 pr-3 font-medium">
                      {FIELD_LABELS[field]}
                    </td>
                    <td className="py-3 pr-3 text-muted-foreground">
                      {formatPct(query.data?.firm[field])}
                    </td>
                    <td className="py-3 pr-3">
                      <Input
                        aria-label={`${FIELD_LABELS[field]} (fraction, e.g. 0.05 for 5%)`}
                        value={draft[field] ?? ''}
                        onChange={(e) =>
                          setDraft((prev) => ({
                            ...prev,
                            [field]: e.target.value,
                          }))
                        }
                        placeholder="inherit firm"
                        className="h-9 max-w-[140px]"
                      />
                      {err ? (
                        <p className="mt-1 text-xs text-destructive" role="alert">
                          {err}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-3 pr-3 font-medium">
                      {formatPct(query.data?.effective[field])}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {formError ? (
          <div
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {formError}
          </div>
        ) : null}

        <div className="flex items-center gap-2">
          <Button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </Button>
          <Label className="text-xs text-muted-foreground">
            Enter fractions (e.g. 0.05 = 5%). Leave blank to inherit the firm cap.
          </Label>
        </div>
      </CardContent>
    </Card>
  );
};

const SettingsAccountRisk: React.FC = () => {
  const accountsQuery = useQuery<ManagedAccount[]>({
    queryKey: ['account-risk-profile', 'accounts'],
    queryFn: async () => {
      const res = (await accountsApi.list()) as ManagedAccount[];
      return Array.isArray(res) ? res : [];
    },
    staleTime: 30_000,
  });

  // Prefetch each account's risk profile so mounting cards stays snappy.
  useQueries({
    queries: (accountsQuery.data ?? []).map((a) => ({
      queryKey: ['account-risk-profile', a.id] as const,
      queryFn: () => accountRiskProfileApi.get(a.id),
      enabled: Boolean(a?.id),
    })),
  });

  return (
    <div className="w-full">
      <div className="mx-auto w-full max-w-[960px] space-y-4">
        <PageHeader
          title="Account risk profile"
          subtitle={
            'Per-account caps that sit on top of the firm-level risk discipline. ' +
            'Firm caps are never loosened — if your value is looser, the firm cap wins.'
          }
        />

        {accountsQuery.isLoading ? (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">
              Loading accounts…
            </CardContent>
          </Card>
        ) : accountsQuery.isError ? (
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-destructive">
                Could not load your accounts.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => accountsQuery.refetch()}
              >
                Retry
              </Button>
            </CardContent>
          </Card>
        ) : !accountsQuery.data || accountsQuery.data.length === 0 ? (
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground">
              Add a broker account from{' '}
              <Link to="/settings/connections" className="underline">
                Connections
              </Link>{' '}
              to configure a risk profile.
            </CardContent>
          </Card>
        ) : (
          accountsQuery.data.map((account) => (
            <AccountRiskCard key={account.id} account={account} />
          ))
        )}
      </div>
    </div>
  );
};

export default SettingsAccountRisk;
