import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { actionRegistry, pushRecentActionId, type ActionContext, type CommandAction, type CommandSection } from '@/lib/actions';
import { formatShortcutParts } from '@/lib/commandShortcut';
import { cn } from '@/lib/utils';

const SECTION_ORDER: CommandSection[] = ['navigation', 'settings', 'actions', 'tickers', 'recent'];

const SECTION_LABEL: Record<CommandSection, string> = {
  navigation: 'Navigation',
  settings: 'Settings & help',
  actions: 'Actions',
  tickers: 'Tickers',
  recent: 'Recent',
};

export interface ShortcutOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ShortcutOverlay({ open, onOpenChange }: ShortcutOverlayProps) {
  const navigate = useNavigate();

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
        /* already viewing */
      },
    };
  }, [navigate, onOpenChange]);

  const runAction = React.useCallback(
    async (action: CommandAction) => {
      const ctx = buildContext();
      await action.run(ctx);
      pushRecentActionId(action.id);
      onOpenChange(false);
    },
    [buildContext, onOpenChange]
  );

  const all = actionRegistry.getAll();
  const grouped = new Map<CommandSection, CommandAction[]>();
  for (const s of SECTION_ORDER) grouped.set(s, []);
  for (const a of all) {
    const list = grouped.get(a.section) ?? [];
    list.push(a);
    grouped.set(a.section, list);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[min(90vh,640px)] max-w-lg overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Registered command palette actions. Press Esc to close.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-6 pb-2">
          {SECTION_ORDER.map((section) => {
            const items = grouped.get(section) ?? [];
            if (!items.length) return null;
            return (
              <div key={section}>
                <div className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                  {SECTION_LABEL[section]}
                </div>
                <ul className="space-y-1">
                  {items.map((action) => (
                    <li key={action.id}>
                      <button
                        type="button"
                        onClick={() => void runAction(action)}
                        className={cn(
                          'flex w-full cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-2 text-left text-sm',
                          'hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none'
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate font-medium">{action.label}</span>
                        {action.shortcut?.length ? (
                          <kbd className="shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
                            {formatShortcutParts(action.shortcut)}
                          </kbd>
                        ) : null}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
