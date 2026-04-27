import React, { useState } from 'react';
import {
  ResponsiveModal as Dialog,
  ResponsiveModalContent as DialogContent,
  ResponsiveModalDescription as DialogDescription,
  ResponsiveModalFooter as DialogFooter,
  ResponsiveModalHeader as DialogHeader,
  ResponsiveModalTitle as DialogTitle,
} from '@/components/ui/responsive-modal';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ExternalLink, Loader2, Pencil, Trash2 } from 'lucide-react';
import type { OAuthConnection } from '@/services/oauth';
import type { WizardBrokerKey } from './brokerCatalog';
import { OAUTH_KEYS_BY_SLUG, LIVE_BROKER_TILES, type BrokerSlug } from './brokerCatalog';
import { formatDateTime } from '@/utils/format';
import { cn } from '@/lib/utils';

const selectSm =
  'h-8 w-[120px] shrink-0 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30';

export interface DetailAccountRow {
  id: number;
  broker: string;
  account_number: string;
  account_name?: string | null;
  account_type?: string;
  is_enabled?: boolean;
  sync_status?: string | null;
  sync_error_message?: string | null;
  last_successful_sync?: string | null;
  total_value?: string | null;
  cash_balance?: string | null;
}

export interface ConnectionDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  wizardBroker: WizardBrokerKey;
  accounts: DetailAccountRow[];
  oauthConnections: OAuthConnection[];
  timezone: string;
  syncingId: number | null;
  busy: boolean;
  schwabConfigured?: boolean;
  onSync: (accountId: number) => void;
  onDeleteAccount: (accountId: number) => void;
  onConnectSchwab: (accountId: number) => void;
  onEditCredentials: (account: DetailAccountRow) => void;
  onUpdateAccountType: (accountId: number, accountType: string) => Promise<void>;
  onToggleTrack: (accountId: number, next: boolean) => Promise<void>;
  onRevokeOAuth: (connectionId: number) => Promise<void>;
}

function wizardKeyToSlug(key: WizardBrokerKey): BrokerSlug | undefined {
  const hit = LIVE_BROKER_TILES.find((t) => t.wizardBroker === key);
  return hit?.slug;
}

export function ConnectionDetailSheet({
  open,
  onOpenChange,
  wizardBroker,
  accounts,
  oauthConnections,
  timezone,
  syncingId,
  busy,
  schwabConfigured,
  onSync,
  onDeleteAccount,
  onConnectSchwab,
  onEditCredentials,
  onUpdateAccountType,
  onToggleTrack,
  onRevokeOAuth,
}: ConnectionDetailSheetProps) {
  const slug = wizardKeyToSlug(wizardBroker);
  const oauthKeys = slug ? OAUTH_KEYS_BY_SLUG[slug] ?? [] : [];
  const relevantOauth = oauthConnections.filter((c) => oauthKeys.includes(c.broker));
  const title = LIVE_BROKER_TILES.find((t) => t.wizardBroker === wizardBroker)?.displayName ?? wizardBroker;
  const [pendingRevokeId, setPendingRevokeId] = useState<number | null>(null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg gap-4" showCloseButton>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="text-left text-muted-foreground">
            Linked accounts and tokens for this broker. Disconnect revokes stored OAuth credentials where applicable.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          {relevantOauth.length > 0 ? (
            <div className="space-y-2 rounded-md border border-border bg-muted/30 p-3">
              <div className="text-xs font-semibold uppercase text-muted-foreground">OAuth connections</div>
              <ul className="space-y-2 text-sm">
                {relevantOauth.map((c) => (
                  <li key={c.id} className="flex flex-row items-center justify-between gap-2">
                    <div>
                      <span className="font-medium text-foreground">{c.broker}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {c.status} · issued {formatDateTime(c.created_at, timezone)}
                      </span>
                    </div>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      disabled={busy}
                      onClick={() => setPendingRevokeId(c.id)}
                    >
                      Disconnect
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase text-muted-foreground">Accounts</div>
            {accounts.length === 0 ? (
              <div className="text-sm text-muted-foreground">No linked accounts yet.</div>
            ) : (
              accounts.map((a) => (
                <div
                  key={a.id}
                  className={cn('space-y-2 rounded-md border border-border bg-background p-3', !a.is_enabled && 'opacity-60')}
                >
                  <div className="flex flex-row flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium text-foreground">{a.account_name || a.account_number}</div>
                      {a.account_number && String(a.account_number) !== String(a.account_name || '') ? (
                        <div className="text-xs text-muted-foreground">{a.account_number}</div>
                      ) : null}
                      {a.last_successful_sync ? (
                        <div className="text-xs text-muted-foreground">
                          Last sync {formatDateTime(a.last_successful_sync, timezone)}
                        </div>
                      ) : null}
                    </div>
                    <select
                      className={selectSm}
                      value={(a.account_type || 'taxable').toUpperCase()}
                      onChange={(e) => void onUpdateAccountType(a.id, e.target.value)}
                    >
                      <option value="TAXABLE">Taxable</option>
                      <option value="IRA">IRA</option>
                      <option value="ROTH_IRA">Roth IRA</option>
                      <option value="HSA">HSA</option>
                      <option value="TRUST">Trust</option>
                    </select>
                  </div>
                  {(a.total_value != null || a.cash_balance != null) && (
                    <div className="text-xs text-muted-foreground">
                      {a.total_value != null ? <>Value {a.total_value}</> : null}
                      {a.total_value != null && a.cash_balance != null ? ' · ' : null}
                      {a.cash_balance != null ? <>Cash {a.cash_balance}</> : null}
                    </div>
                  )}
                  <div className="flex flex-row items-center gap-2">
                    <Checkbox
                      checked={!!a.is_enabled}
                      onCheckedChange={(v) => void onToggleTrack(a.id, v === true)}
                    />
                    <span className="text-xs font-medium text-foreground">{a.is_enabled ? 'Track in portfolio' : 'Not tracked'}</span>
                    {a.sync_status ? (
                      <Badge variant="outline" className="font-normal">
                        {a.sync_status}
                      </Badge>
                    ) : null}
                  </div>
                  {a.sync_error_message ? (
                    <div className="text-xs text-destructive">{a.sync_error_message}</div>
                  ) : null}
                  <div className="flex flex-row flex-wrap gap-2">
                    {String(a.broker || '').toLowerCase() === 'schwab' && (
                      <Button
                        type="button"
                        size="xs"
                        variant="outline"
                        onClick={() => onConnectSchwab(a.id)}
                        disabled={schwabConfigured === false}
                      >
                        Link Schwab <ExternalLink className="ml-1 inline size-3" aria-hidden />
                      </Button>
                    )}
                    {(String(a.broker || '').toLowerCase() === 'tastytrade' ||
                      String(a.broker || '').toLowerCase() === 'ibkr') && (
                      <Button type="button" size="xs" variant="outline" onClick={() => onEditCredentials(a)}>
                        <Pencil className="mr-1 size-3" aria-hidden />
                        Credentials
                      </Button>
                    )}
                    <Button type="button" size="xs" onClick={() => onSync(a.id)} disabled={syncingId === a.id}>
                      {syncingId === a.id ? <Loader2 className="mr-1 size-3 animate-spin" aria-hidden /> : null}
                      Sync
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      aria-label="Delete account"
                      onClick={() => onDeleteAccount(a.id)}
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        {pendingRevokeId != null ? (
          <div className="rounded-md border border-border bg-muted/40 p-3 text-sm">
            <div className="mb-2 font-medium text-foreground">Revoke this OAuth connection?</div>
            <div className="mb-3 text-muted-foreground">
              Tokens are removed locally; you can run Connect again to link the broker.
            </div>
            <div className="flex flex-row justify-end gap-2">
              <Button type="button" size="sm" variant="ghost" onClick={() => setPendingRevokeId(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={busy}
                onClick={async () => {
                  if (pendingRevokeId == null) return;
                  try {
                    await onRevokeOAuth(pendingRevokeId);
                    setPendingRevokeId(null);
                  } catch {
                    /* parent surfaces toast */
                  }
                }}
              >
                {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Confirm disconnect
              </Button>
            </div>
          </div>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
