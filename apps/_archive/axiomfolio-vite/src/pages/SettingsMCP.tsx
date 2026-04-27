/**
 * SettingsMCP — manage Model Context Protocol bearer tokens.
 *
 * Each token grants a single MCP client (ChatGPT, Claude, Cursor, etc.)
 * read-only access to this user's portfolio via JSON-RPC. The plaintext
 * token is shown EXACTLY ONCE on creation; we never retrieve it again.
 *
 * Distinguishes loading / error / empty / data states explicitly to
 * comply with the no-silent-fallback rule (a long-loading list must not
 * masquerade as "you have zero tokens").
 */

import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import hotToast from 'react-hot-toast';
import { Copy, KeyRound, Loader2, ShieldAlert, Trash2 } from 'lucide-react';

import { PageHeader } from '../components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

import {
  handleApiError,
  mcpApi,
  type MCPTokenCreateResponse,
  type MCPTokenSummary,
} from '../services/api';

const QUERY_KEY = ['mcp', 'tokens'] as const;

const formatDateTime = (iso: string | null): string => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
};

const tokenStatusBadge = (token: MCPTokenSummary) => {
  if (token.revoked_at) {
    return (
      <Badge variant="destructive" className="font-normal">
        Revoked
      </Badge>
    );
  }
  if (!token.is_active) {
    return (
      <Badge variant="secondary" className="font-normal">
        Expired
      </Badge>
    );
  }
  return (
    <Badge
      variant="outline"
      className="border-emerald-500/40 bg-emerald-500/10 font-normal text-emerald-800 dark:text-emerald-200"
    >
      Active
    </Badge>
  );
};

const SettingsMCP: React.FC = () => {
  const queryClient = useQueryClient();

  const tokensQuery = useQuery<MCPTokenSummary[]>({
    queryKey: QUERY_KEY,
    queryFn: mcpApi.list,
  });

  const [name, setName] = React.useState('');
  const [piiConsent, setPiiConsent] = React.useState(false);
  const [created, setCreated] = React.useState<MCPTokenCreateResponse | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; pii_tax_lot_consent: boolean }) =>
      mcpApi.create(payload),
    onSuccess: (data) => {
      setCreated(data);
      setName('');
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => hotToast.error(handleApiError(err)),
  });

  const revokeMutation = useMutation({
    mutationFn: (tokenId: number) => mcpApi.revoke(tokenId),
    onSuccess: () => {
      hotToast.success('Token revoked');
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => hotToast.error(handleApiError(err)),
  });

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      hotToast.error('Token name is required');
      return;
    }
    createMutation.mutate({
      name: trimmed,
      pii_tax_lot_consent: piiConsent,
    });
  };

  const handleCopy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      hotToast.success('Copied to clipboard');
    } catch {
      hotToast.error('Could not copy. Select and copy manually.');
    }
  };

  const renderTokenList = () => {
    if (tokensQuery.isLoading) {
      return (
        <div className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading tokens…
        </div>
      );
    }
    if (tokensQuery.isError) {
      return (
        <div className="flex flex-col items-start gap-2 px-4 py-6">
          <p className="text-sm text-destructive">Could not load tokens.</p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => tokensQuery.refetch()}
          >
            Retry
          </Button>
        </div>
      );
    }
    const rows = tokensQuery.data ?? [];
    if (rows.length === 0) {
      return (
        <div className="px-4 py-6 text-sm text-muted-foreground">
          No tokens yet. Create one above to connect an MCP client.
        </div>
      );
    }
    return (
      <ul className="divide-y divide-border">
        {rows.map((token) => (
          <li
            key={token.id}
            className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium text-foreground">{token.name}</span>
                {tokenStatusBadge(token)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Created {formatDateTime(token.created_at)} · Expires{' '}
                {formatDateTime(token.expires_at)} · Last used{' '}
                {formatDateTime(token.last_used_at)}
              </p>
            </div>
            <div className="shrink-0">
              {token.revoked_at ? null : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive"
                  disabled={revokeMutation.isPending && revokeMutation.variables === token.id}
                  onClick={() => {
                    if (window.confirm(`Revoke token "${token.name}"? This cannot be undone.`)) {
                      revokeMutation.mutate(token.id);
                    }
                  }}
                >
                  <Trash2 className="size-4" />
                  <span className="ml-1.5">Revoke</span>
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="w-full">
      <div className="mx-auto w-full max-w-[960px]">
        <PageHeader
          title="MCP Tokens"
          subtitle="Bearer tokens that let external AI clients (ChatGPT, Claude, Cursor) read your portfolio over the Model Context Protocol."
        />

        <div className="mt-4 flex flex-col gap-4">
          <Card>
            <CardContent className="space-y-4 pt-6">
              <div className="flex items-center gap-2">
                <KeyRound className="size-4 text-muted-foreground" />
                <h2 className="font-heading font-semibold text-foreground">
                  Create a new token
                </h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Each token is unique to one client. The plaintext value is
                displayed exactly once at creation and cannot be retrieved
                later. Tokens default to a 365-day lifetime and are scoped
                to read-only portfolio data.
              </p>
              <form
                onSubmit={handleCreate}
                className="flex flex-col gap-3 sm:flex-row sm:items-end"
              >
                <div className="flex-1">
                  <Label htmlFor="mcp-token-name" className="mb-1.5 block text-muted-foreground">
                    Name
                  </Label>
                  <Input
                    id="mcp-token-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. ChatGPT Desktop"
                    maxLength={120}
                    disabled={createMutation.isPending}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={piiConsent}
                    onChange={(e) => setPiiConsent(e.target.checked)}
                  />
                  Allow tax-lot MCP scope (PII)
                </label>
                <Button
                  type="submit"
                  disabled={createMutation.isPending || !name.trim()}
                  className="sm:w-auto"
                >
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      <span className="ml-1.5">Creating…</span>
                    </>
                  ) : (
                    'Create token'
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="px-0 pt-6">
              <div className="px-4 pb-3">
                <h2 className="font-heading font-semibold text-foreground">Active tokens</h2>
                <p className="text-sm text-muted-foreground">
                  Manage tokens you've issued. Revoke any you no longer use.
                </p>
              </div>
              {renderTokenList()}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog
        open={created !== null}
        onOpenChange={(open) => {
          if (!open) setCreated(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldAlert className="size-5 text-amber-500" />
              Copy your new token now
            </DialogTitle>
            <DialogDescription>
              This is the only time the plaintext value will be shown. Store
              it in your MCP client immediately. If you lose it, revoke this
              token and create a new one.
            </DialogDescription>
          </DialogHeader>
          {created && (
            <div className="space-y-3">
              <div>
                <Label className="mb-1.5 block text-muted-foreground">Token</Label>
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={created.token}
                    className="font-mono text-xs"
                    onFocus={(e) => e.currentTarget.select()}
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    onClick={() => handleCopy(created.token)}
                    aria-label="Copy token to clipboard"
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
                <p className="font-medium text-foreground">Endpoint</p>
                <code className="mt-1 block break-all font-mono">
                  POST {window.location.origin}/api/v1/mcp/jsonrpc
                </code>
                <p className="mt-2">
                  Send the token in the <code className="font-mono">Authorization: Bearer …</code>{' '}
                  header. JSON-RPC 2.0 methods: <code className="font-mono">tools/list</code>,{' '}
                  <code className="font-mono">tools/call</code>.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreated(null)}>
              I've copied it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SettingsMCP;
