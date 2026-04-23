/**
 * TopBarAccountSelector — the sleek global account filter that lives in the
 * dashboard top bar.
 *
 * Design goals (founder feedback: "sleeker ofcourse"):
 *   - Pill-shaped trigger with broker monogram, nickname, and an optional
 *     count badge when >1 accounts are wired.
 *   - Dropdown grouped by broker (Schwab, IBKR, Tastytrade, …) with masked
 *     account number, account-type chip, and live NAV (tabular-nums).
 *   - Search input appears once >5 accounts are connected.
 *   - Explicit loading / error / empty / data states — never a silent "0".
 *   - Keyboard-first (Radix DropdownMenu: arrow keys + Enter + Esc).
 *   - On <768px viewports collapses to an icon + count + chevron; tooltip
 *     labels the control.
 *
 * State is delegated to `AccountContext` (single source of truth) — this
 * component never touches localStorage directly. NAV figures reuse
 * `useAccountBalances()` so the accounts list query is not duplicated.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Building2, ChevronDown, Plug, Search, Wallet } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';

import { useAccountContext, type BrokerAccount } from '@/context/AccountContext';
import { useAccountBalances } from '@/hooks/usePortfolio';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { formatMoney } from '@/utils/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

const BROKER_LABELS: Record<string, string> = {
  schwab: 'Charles Schwab',
  ibkr: 'Interactive Brokers',
  tastytrade: 'Tastytrade',
  fidelity: 'Fidelity',
  robinhood: 'Robinhood',
};

// Order brokers so the dropdown is deterministic across renders.
const BROKER_ORDER = ['schwab', 'ibkr', 'tastytrade', 'fidelity', 'robinhood'];

function brokerKey(raw: string | undefined | null): string {
  return (raw || '').trim().toLowerCase();
}

function brokerLabel(raw: string | undefined | null): string {
  const k = brokerKey(raw);
  if (!k) return 'Other';
  return BROKER_LABELS[k] ?? (raw || 'Other');
}

function brokerMonogram(raw: string | undefined | null): string {
  const label = brokerLabel(raw);
  // Strip trailing qualifiers and take first two letters of the brand.
  const base = label.replace(/\(.*?\)/g, '').trim();
  const tokens = base.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return '?';
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase();
  return (tokens[0][0] + tokens[1][0]).toUpperCase();
}

function maskedTail(accountNumber: string | undefined | null): string {
  const s = (accountNumber || '').trim();
  if (!s) return '';
  const tail = s.slice(-4);
  return `••${tail}`;
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

function prettyAccountType(raw: string | undefined | null): string | null {
  const v = (raw || '').trim();
  if (!v) return null;
  const lower = v.toLowerCase();
  if (lower.includes('ira')) return 'IRA';
  if (lower.includes('roth')) return 'Roth';
  if (lower.includes('joint')) return 'Joint';
  if (lower.includes('margin')) return 'Margin';
  if (lower.includes('cash')) return 'Cash';
  if (lower.includes('individual')) return 'Individual';
  if (lower.includes('retirement')) return 'Retirement';
  if (lower.includes('trust')) return 'Trust';
  // Fall back to title case (max 8 chars so the chip stays compact).
  const title = v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
  return title.length > 10 ? `${title.slice(0, 9)}…` : title;
}

interface BalanceLike {
  account_id?: number;
  account_number?: string;
  broker?: string;
  net_liquidation?: number | string | null;
}

function buildNavLookup(balances: BalanceLike[] | undefined): Map<string, number> {
  const map = new Map<string, number>();
  if (!Array.isArray(balances)) return map;
  for (const row of balances) {
    const nav = row?.net_liquidation == null ? null : Number(row.net_liquidation);
    if (nav == null || !Number.isFinite(nav)) continue;
    if (row.account_number) map.set(row.account_number, nav);
    if (typeof row.account_id === 'number') map.set(`id:${row.account_id}`, nav);
  }
  return map;
}

function groupByBroker(accounts: BrokerAccount[]): Array<{ broker: string; items: BrokerAccount[] }> {
  const buckets = new Map<string, BrokerAccount[]>();
  for (const a of accounts) {
    const k = brokerKey(a.broker) || 'other';
    const list = buckets.get(k) ?? [];
    list.push(a);
    buckets.set(k, list);
  }
  const keys = Array.from(buckets.keys());
  keys.sort((a, b) => {
    const ia = BROKER_ORDER.indexOf(a);
    const ib = BROKER_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
  return keys.map((k) => ({
    broker: k,
    items: (buckets.get(k) ?? []).slice().sort((a, b) => {
      const an = (a.account_name || a.account_number || '').toLowerCase();
      const bn = (b.account_name || b.account_number || '').toLowerCase();
      return an.localeCompare(bn);
    }),
  }));
}

function matchesSearch(account: BrokerAccount, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    account.account_name,
    account.account_number,
    account.account_type,
    account.broker,
    brokerLabel(account.broker),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return hay.includes(q);
}

function BrokerMonogram({ broker, className }: { broker: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-flex size-5 shrink-0 items-center justify-center rounded-md bg-muted text-[9px] font-semibold text-foreground/80',
        className
      )}
    >
      {brokerMonogram(broker)}
    </span>
  );
}

interface TriggerLabelProps {
  selected: string;
  accounts: BrokerAccount[];
  isCompact: boolean;
  accountCount: number;
}

function triggerDisplayName(selected: string, accounts: BrokerAccount[]): string {
  if (!selected || selected === 'all') return 'All accounts';
  if (selected === 'taxable') return 'Taxable';
  if (selected === 'ira') return 'Retirement';
  if (selected === 'hsa') return 'HSA';
  const a = accounts.find((x) => x.account_number === selected || String(x.id) === selected);
  if (!a) return 'All accounts';
  const raw = a.account_name?.trim() || a.account_number || 'Account';
  return truncate(raw, 20);
}

function isBucketSelection(selected: string): boolean {
  return selected === 'all' || selected === 'taxable' || selected === 'ira' || selected === 'hsa';
}

interface BucketInfo {
  id: 'taxable' | 'ira' | 'hsa';
  label: string;
  predicate: (accountType: string) => boolean;
}

const BUCKETS: BucketInfo[] = [
  {
    id: 'taxable',
    label: 'Taxable',
    // Taxable is "everything that is not retirement and not HSA" so the
    // sum across buckets covers every tracked account exactly once.
    predicate: (t) =>
      !t.includes('ira') &&
      !t.includes('retire') &&
      !t.includes('401') &&
      !t.includes('hsa') &&
      !t.includes('health_savings'),
  },
  {
    id: 'ira',
    label: 'Retirement',
    predicate: (t) => t.includes('ira') || t.includes('retire') || t.includes('401'),
  },
  {
    id: 'hsa',
    label: 'HSA',
    predicate: (t) => t.includes('hsa') || t.includes('health_savings'),
  },
];

function availableBuckets(accounts: BrokerAccount[]): BucketInfo[] {
  return BUCKETS.filter((bucket) =>
    accounts.some((a) => bucket.predicate((a.account_type || '').toLowerCase())),
  );
}

function TriggerLabel({ selected, accounts, isCompact, accountCount }: TriggerLabelProps) {
  const label = triggerDisplayName(selected, accounts);
  const showCount = accountCount > 1;
  const selectedBroker = useMemo(() => {
    if (isBucketSelection(selected)) return null;
    return accounts.find((x) => x.account_number === selected || String(x.id) === selected)?.broker ?? null;
  }, [selected, accounts]);

  return (
    <span
      className={cn(
        'flex min-w-0 items-center gap-2',
        isCompact && 'gap-1.5'
      )}
    >
      {selectedBroker ? (
        <BrokerMonogram broker={selectedBroker} />
      ) : (
        <Wallet className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      )}
      {!isCompact ? (
        <span className="truncate text-sm font-medium">{label}</span>
      ) : null}
      {showCount ? (
        <Badge
          variant="secondary"
          className="h-4 min-w-4 shrink-0 px-1 text-[10px] tabular-nums"
          aria-label={`${accountCount} accounts`}
        >
          {accountCount}
        </Badge>
      ) : null}
    </span>
  );
}

interface RowProps {
  account: BrokerAccount;
  isSelected: boolean;
  onSelect: () => void;
  navDisplay: string;
  navAriaLabel: string;
}

function AccountRow({ account, isSelected, onSelect, navDisplay, navAriaLabel }: RowProps) {
  const typeChip = prettyAccountType(account.account_type);
  const nickname = account.account_name?.trim() || account.account_number || 'Account';
  return (
    <DropdownMenu.Item
      data-testid="tbas-account-row"
      onSelect={(event) => {
        event.preventDefault();
        onSelect();
      }}
      className={cn(
        'group/row flex cursor-default select-none items-center gap-2.5 rounded-md px-2 py-2 text-sm outline-none',
        'focus:bg-accent focus:text-accent-foreground',
        'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        isSelected && 'bg-accent/50 text-foreground',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0'
      )}
      aria-current={isSelected ? 'true' : undefined}
    >
      <BrokerMonogram broker={account.broker ?? ''} className="size-6 rounded-lg text-[10px]" />
      <span className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium">{truncate(nickname, 24)}</span>
          {typeChip ? (
            <Badge
              variant="outline"
              className="h-4 shrink-0 border-border bg-transparent px-1.5 text-[10px] font-medium text-muted-foreground"
            >
              {typeChip}
            </Badge>
          ) : null}
        </span>
        <span className="truncate text-[11px] text-muted-foreground tabular-nums">
          {maskedTail(account.account_number)}
        </span>
      </span>
      <span
        className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground"
        aria-label={navAriaLabel}
      >
        {navDisplay}
      </span>
    </DropdownMenu.Item>
  );
}

export interface TopBarAccountSelectorProps {
  /** Force the collapsed (icon-only) trigger — useful for mobile layouts. */
  compact?: boolean;
}

export const TopBarAccountSelector: React.FC<TopBarAccountSelectorProps> = ({ compact = false }) => {
  const { accounts, loading, error, selected, setSelected, refetch } = useAccountContext();
  const balancesQuery = useAccountBalances();
  const { currency } = useUserPreferences();

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement | null>(null);

  const showSearch = accounts.length > 5;

  useEffect(() => {
    if (!isOpen) {
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !showSearch) return;
    // Defer to ensure Radix has mounted the content and moved focus.
    const id = window.setTimeout(() => {
      searchRef.current?.focus();
    }, 10);
    return () => window.clearTimeout(id);
  }, [isOpen, showSearch]);

  const balances = balancesQuery.data as BalanceLike[] | undefined;
  const navLookup = useMemo(() => buildNavLookup(balances), [balances]);
  const balancesLoading = balancesQuery.isPending;
  const balancesErrored = balancesQuery.isError;

  const filtered = useMemo(() => accounts.filter((a) => matchesSearch(a, query)), [accounts, query]);
  const groups = useMemo(() => groupByBroker(filtered), [filtered]);
  const buckets = useMemo(() => availableBuckets(accounts), [accounts]);

  const isAllSelected = !selected || selected === 'all';
  const triggerAriaLabel = `Account filter: ${triggerDisplayName(selected, accounts)}`;

  const navDisplayFor = (account: BrokerAccount): { text: string; aria: string } => {
    if (balancesLoading) return { text: '—', aria: 'Balance loading' };
    if (balancesErrored) return { text: '—', aria: 'Balance unavailable' };
    const key = account.account_number;
    let nav = key ? navLookup.get(key) : undefined;
    if (nav == null && account.id != null) nav = navLookup.get(`id:${account.id}`);
    if (nav == null) return { text: '—', aria: 'Balance unavailable' };
    const formatted = formatMoney(nav, currency, { maximumFractionDigits: 0, minimumFractionDigits: 0 });
    return { text: formatted, aria: `Net liquidation ${formatted}` };
  };

  const triggerButton = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      aria-label={triggerAriaLabel}
      className={cn(
        'h-8 min-w-0 gap-1.5 rounded-full border-border/80 bg-background/80 px-2.5 font-normal backdrop-blur',
        'hover:bg-muted/70',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0',
        !compact && 'max-w-[240px]',
        compact && 'px-2'
      )}
      data-compact={compact ? 'true' : 'false'}
    >
      <TriggerLabel
        selected={selected}
        accounts={accounts}
        isCompact={compact}
        accountCount={accounts.length}
      />
      <ChevronDown className="size-3.5 shrink-0 opacity-60" aria-hidden />
    </Button>
  );

  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger asChild>
        {compact ? (
          <Tooltip>
            <TooltipTrigger asChild>{triggerButton}</TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              Filter by account
            </TooltipContent>
          </Tooltip>
        ) : (
          triggerButton
        )}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          // Prevent the dropdown from fighting the search input for focus.
          onCloseAutoFocus={(event) => {
            if (showSearch) event.preventDefault();
          }}
          className={cn(
            'z-50 max-h-[min(28rem,75vh)] w-[320px] overflow-hidden rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lg',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2'
          )}
        >
          {showSearch ? (
            <div className="sticky top-0 z-10 border-b border-border/60 bg-popover p-1.5">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  ref={searchRef}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    // Keep Radix from intercepting typeable characters so the
                    // search field actually receives input.
                    if (
                      event.key === 'ArrowDown' ||
                      event.key === 'ArrowUp' ||
                      event.key === 'Enter' ||
                      event.key === 'Escape'
                    ) {
                      return;
                    }
                    event.stopPropagation();
                  }}
                  placeholder="Search accounts…"
                  aria-label="Search accounts"
                  className="h-8 pl-7 text-sm"
                />
              </div>
            </div>
          ) : null}

          <div className="max-h-[24rem] overflow-y-auto p-1">
            <DropdownMenu.Item
              data-testid="tbas-all-accounts"
              onSelect={(event) => {
                event.preventDefault();
                setSelected('all');
                setIsOpen(false);
              }}
              className={cn(
                'mb-0.5 flex cursor-default select-none items-center gap-2.5 rounded-md px-2 py-2 text-sm outline-none',
                'focus:bg-accent focus:text-accent-foreground',
                'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0',
                isAllSelected && 'bg-accent/60 text-foreground'
              )}
              aria-current={isAllSelected ? 'true' : undefined}
            >
              <span
                aria-hidden
                className="inline-flex size-6 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground/80"
              >
                <Building2 className="size-3.5" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col leading-tight">
                <span className="truncate text-sm font-medium">All accounts</span>
                <span className="truncate text-[11px] text-muted-foreground">
                  Combined portfolio view
                </span>
              </span>
              {accounts.length > 0 ? (
                <Badge
                  variant="secondary"
                  className="h-4 shrink-0 px-1.5 text-[10px] tabular-nums"
                  aria-label={`${accounts.length} accounts`}
                >
                  {accounts.length}
                </Badge>
              ) : null}
            </DropdownMenu.Item>

            {buckets.length > 1 && !loading && !error && accounts.length > 0 ? (
              <div
                className="mt-0.5 flex flex-wrap gap-1 px-1 pb-1"
                role="group"
                aria-label="Filter by account category"
              >
                {buckets.map((bucket) => {
                  const isSelected = selected === bucket.id;
                  return (
                    <DropdownMenu.Item
                      key={bucket.id}
                      data-testid={`tbas-bucket-${bucket.id}`}
                      onSelect={(event) => {
                        event.preventDefault();
                        setSelected(bucket.id);
                        setIsOpen(false);
                      }}
                      className={cn(
                        'inline-flex cursor-default select-none items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] outline-none transition-colors',
                        'focus:bg-accent focus:text-accent-foreground',
                        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0',
                        isSelected
                          ? 'border-primary bg-primary/10 text-foreground'
                          : 'border-border/80 bg-transparent text-muted-foreground hover:border-border hover:text-foreground',
                      )}
                      aria-current={isSelected ? 'true' : undefined}
                    >
                      {bucket.label}
                    </DropdownMenu.Item>
                  );
                })}
              </div>
            ) : null}

            {loading ? (
              <div
                role="status"
                aria-live="polite"
                aria-label="Loading accounts"
                className="flex flex-col gap-1 px-2 py-1"
              >
                {[0, 1, 2].map((i) => (
                  <div key={i} className="flex items-center gap-2.5 py-1.5">
                    <Skeleton className="size-6 rounded-lg" />
                    <div className="flex flex-1 flex-col gap-1">
                      <Skeleton className="h-3 w-[60%]" />
                      <Skeleton className="h-2.5 w-[40%]" />
                    </div>
                    <Skeleton className="h-3 w-12" />
                  </div>
                ))}
              </div>
            ) : error ? (
              <div role="alert" className="flex flex-col gap-2 px-2 py-3 text-sm">
                <span className="inline-flex items-center gap-2 text-foreground">
                  <AlertTriangle className="size-4 shrink-0 text-[rgb(var(--status-danger))]" aria-hidden />
                  <span className="truncate">Couldn’t load accounts</span>
                </span>
                <p className="text-xs text-muted-foreground">{error}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 self-start"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    refetch();
                  }}
                >
                  Retry
                </Button>
              </div>
            ) : accounts.length === 0 ? (
              <div className="flex flex-col gap-2 px-2 py-3 text-sm">
                <span className="inline-flex items-center gap-2 text-foreground">
                  <Plug className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <span>No brokers connected</span>
                </span>
                <p className="text-xs text-muted-foreground">
                  Link a brokerage account to filter your portfolio.
                </p>
                <Button asChild variant="outline" size="sm" className="h-7 self-start">
                  <Link
                    to="/settings/connections"
                    onClick={() => setIsOpen(false)}
                  >
                    Connect broker
                  </Link>
                </Button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-2 py-4 text-center text-xs text-muted-foreground">
                No accounts match “{query.trim()}”.
              </div>
            ) : (
              groups.map((group) => {
                const selectedInGroup = group.items.some(
                  (a) => a.account_number === selected || String(a.id) === selected
                );
                return (
                  <DropdownMenu.Group key={group.broker} className="mt-1">
                    <DropdownMenu.Label
                      className={cn(
                        'flex items-center gap-1.5 px-2 pb-1 pt-1.5 text-[10px] font-semibold tracking-[0.08em] text-muted-foreground uppercase',
                        selectedInGroup && 'text-foreground'
                      )}
                    >
                      <BrokerMonogram broker={group.broker} className="size-4 rounded-[5px] text-[8px]" />
                      <span className="truncate">{brokerLabel(group.broker)}</span>
                    </DropdownMenu.Label>
                    {group.items.map((account) => {
                      const isSelected =
                        selected === account.account_number || selected === String(account.id);
                      const { text, aria } = navDisplayFor(account);
                      return (
                        <AccountRow
                          key={account.id ?? account.account_number}
                          account={account}
                          isSelected={isSelected}
                          navDisplay={text}
                          navAriaLabel={aria}
                          onSelect={() => {
                            setSelected(account.account_number);
                            setIsOpen(false);
                          }}
                        />
                      );
                    })}
                  </DropdownMenu.Group>
                );
              })
            )}
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};

export default TopBarAccountSelector;
