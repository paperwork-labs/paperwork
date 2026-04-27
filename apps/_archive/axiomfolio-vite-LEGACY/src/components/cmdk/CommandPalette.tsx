import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Command } from 'cmdk';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import {
  actionRegistry,
  getRecentActionIds,
  matchesActionQuery,
  pushRecentActionId,
  type ActionContext,
  type CommandAction,
} from '@/lib/actions';
import { marketDataApi } from '@/services/api';
import { FALLBACK_TICKER_SYMBOLS, looksLikeTickerQuery } from '@/components/cmdk/tickerSymbols';
import type { MarketSnapshotRow } from '@/types/market';

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  if (target.closest('[role="combobox"]')) return true;
  return false;
}

function useDebouncedValue<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRequestShortcutOverlay?: () => void;
}

export function CommandPalette({ open, onOpenChange, onRequestShortcutOverlay }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [search, setSearch] = React.useState('');
  const debouncedSearch = useDebouncedValue(search, 220);
  const tickerQuery = debouncedSearch.trim().toUpperCase();
  const tickerEnabled = open && looksLikeTickerQuery(debouncedSearch);

  const snapshotQuery = useQuery({
    queryKey: ['cmdk-snapshot-symbol-search', tickerQuery],
    queryFn: () =>
      marketDataApi.getSnapshotTable({
        search: tickerQuery,
        limit: 15,
        sort_by: 'symbol',
        sort_dir: 'asc',
      }),
    enabled: tickerEnabled,
    staleTime: 60_000,
    retry: 1,
  });

  const fallbackTickers = React.useMemo(() => {
    if (!tickerEnabled) return [];
    const q = tickerQuery;
    return FALLBACK_TICKER_SYMBOLS.filter((s) => s.includes(q) || q.includes(s)).slice(0, 15);
  }, [tickerEnabled, tickerQuery]);

  const tickerRows: MarketSnapshotRow[] = snapshotQuery.data?.rows ?? [];
  const showFallbackTickers =
    tickerEnabled && !snapshotQuery.isFetching && tickerRows.length === 0 && fallbackTickers.length > 0;

  React.useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        onOpenChange(false);
        return;
      }
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        if (isTypingTarget(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open, onOpenChange]);

  const buildContext = React.useCallback((): ActionContext => {
    return {
      navigate: (to: string) => {
        navigate(to);
        onOpenChange(false);
      },
      toast: (msg, opts) => {
        if (opts?.type === 'error') toast.error(msg);
        else if (opts?.type === 'success') toast.success(msg);
        else toast(msg);
      },
      openShortcutHelp: () => {
        onOpenChange(false);
        onRequestShortcutOverlay?.();
      },
    };
  }, [navigate, onOpenChange, onRequestShortcutOverlay]);

  const recentIds = React.useMemo(() => getRecentActionIds(), [open]);
  const recentIdSet = React.useMemo(() => new Set(recentIds), [recentIds]);

  const recentEntries = React.useMemo(() => {
    return recentIds
      .map((id) => {
        if (id.startsWith('ticker:')) {
          const sym = id.slice('ticker:'.length).toUpperCase();
          if (!sym) return null;
          const sq = search.trim().toUpperCase();
          if (sq && !sym.includes(sq) && !sq.includes(sym)) return null;
          return { kind: 'ticker' as const, id, symbol: sym };
        }
        const action = actionRegistry.getById(id);
        if (!action || !matchesActionQuery(search, action)) return null;
        return { kind: 'action' as const, id, action };
      })
      .filter((x): x is NonNullable<typeof x> => x != null);
  }, [recentIds, search]);

  const registryMatches = React.useMemo(() => {
    return actionRegistry.search(search).filter((a) => !recentIdSet.has(a.id));
  }, [search, recentIdSet]);

  const runAction = React.useCallback(
    async (action: CommandAction) => {
      const ctx = buildContext();
      await action.run(ctx);
      pushRecentActionId(action.id);
      onOpenChange(false);
    },
    [buildContext, onOpenChange]
  );

  const goTicker = React.useCallback(
    (symbol: string) => {
      const sym = symbol.trim().toUpperCase();
      navigate(`/market/tracked?symbols=${encodeURIComponent(sym)}`);
      pushRecentActionId(`ticker:${sym}`);
      onOpenChange(false);
    },
    [navigate, onOpenChange]
  );

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      shouldFilter={false}
      className={cn(
        'fixed z-[100] overflow-hidden font-sans shadow-2xl',
        'font-[family-name:var(--font-sans,ui-sans-serif,system-ui)]',
        'max-md:inset-0 max-md:m-0 max-md:max-h-[100dvh] max-md:w-full max-md:max-w-none max-md:rounded-none',
        'md:left-1/2 md:top-[15%] md:w-full md:max-w-xl md:-translate-x-1/2',
        'border border-border bg-popover/95 text-popover-foreground ring-1 ring-foreground/10',
        'supports-backdrop-filter:backdrop-blur-md',
        'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
        'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
        'duration-150'
      )}
    >
      <div className="border-b border-border px-3 py-2">
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Search pages, tickers, actions…"
          className={cn(
            'w-full border-0 bg-transparent py-2 text-sm text-foreground outline-none',
            'placeholder:text-muted-foreground'
          )}
        />
      </div>
      <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
        <Command.Empty className="py-8 text-center text-sm text-muted-foreground">No matches.</Command.Empty>

        {recentEntries.length > 0 && (
          <Command.Group
            heading="Recent"
            className="mb-2 text-xs font-medium text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
          >
            {recentEntries.map((entry) =>
              entry.kind === 'ticker' ? (
                <Command.Item
                  key={entry.id}
                  value={`recent ticker ${entry.symbol}`}
                  onSelect={() => goTicker(entry.symbol)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm',
                    'aria-selected:bg-accent aria-selected:text-accent-foreground'
                  )}
                >
                  <span className="font-mono text-xs font-medium">{entry.symbol}</span>
                  <span className="text-xs text-muted-foreground">Open tracked</span>
                </Command.Item>
              ) : (
                <Command.Item
                  key={`recent-${entry.action.id}`}
                  value={`recent ${entry.action.id} ${entry.action.label}`}
                  onSelect={() => void runAction(entry.action)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm',
                    'aria-selected:bg-accent aria-selected:text-accent-foreground'
                  )}
                >
                  {entry.action.icon ? (
                    <entry.action.icon className="size-4 shrink-0 opacity-70" size={16} />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{entry.action.label}</div>
                    {entry.action.description ? (
                      <div className="truncate text-xs text-muted-foreground">{entry.action.description}</div>
                    ) : null}
                  </div>
                </Command.Item>
              )
            )}
          </Command.Group>
        )}

        <Command.Group
          heading="Navigation & actions"
          className="mb-2 text-xs font-medium text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
        >
          {registryMatches.map((action) => (
            <Command.Item
              key={action.id}
              value={`${action.id} ${action.label} ${(action.keywords || []).join(' ')}`}
              onSelect={() => void runAction(action)}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm',
                'aria-selected:bg-accent aria-selected:text-accent-foreground'
              )}
            >
              {action.icon ? <action.icon className="size-4 shrink-0 opacity-70" size={16} /> : null}
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{action.label}</div>
                {action.description ? (
                  <div className="truncate text-xs text-muted-foreground">{action.description}</div>
                ) : null}
              </div>
            </Command.Item>
          ))}
        </Command.Group>

        {tickerEnabled && (
          <Command.Group
            heading="Tickers"
            className="text-xs font-medium text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
          >
            {snapshotQuery.isFetching && (
              <div className="px-2 py-2 text-sm text-muted-foreground">Loading symbols…</div>
            )}
            {!snapshotQuery.isFetching &&
              tickerRows.map((row) => {
                const sym = String(row.symbol || '').toUpperCase();
                if (!sym) return null;
                const px = row.current_price;
                return (
                  <Command.Item
                    key={sym}
                    value={`ticker ${sym}`}
                    onSelect={() => goTicker(sym)}
                    className={cn(
                      'flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-2 text-sm',
                      'aria-selected:bg-accent aria-selected:text-accent-foreground'
                    )}
                  >
                    <span className="font-mono font-medium">{sym}</span>
                    {typeof px === 'number' ? (
                      <span className="text-xs text-muted-foreground">{px.toFixed(2)}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground"> </span>
                    )}
                  </Command.Item>
                );
              })}
            {showFallbackTickers &&
              fallbackTickers.map((sym) => (
                <Command.Item
                  key={`fb-${sym}`}
                  value={`ticker ${sym}`}
                  onSelect={() => goTicker(sym)}
                  className={cn(
                    'flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-2 text-sm',
                    'aria-selected:bg-accent aria-selected:text-accent-foreground'
                  )}
                >
                  <span className="font-mono font-medium">{sym}</span>
                  <span className="text-xs text-muted-foreground"> </span>
                </Command.Item>
              ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
