import React from 'react';
import { ChevronDown } from 'lucide-react';
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface CompactAccountSelectorProps {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  accounts: Array<{ account_number: string; account_name?: string }>;
  width?: string | number;
}

function labelForValue(
  value: string,
  accounts: Array<{ account_number: string; account_name?: string }>
): string {
  if (value === 'all') return 'All Accounts';
  if (value === 'taxable') return 'Taxable';
  if (value === 'ira') return 'Tax-Deferred (IRA)';
  const a = accounts.find((x) => x.account_number === value);
  return a?.account_name || a?.account_number || value;
}

export const CompactAccountSelector: React.FC<CompactAccountSelectorProps> = ({
  value,
  onChange,
  disabled,
  accounts,
  width = '100%',
}) => {
  const items: { value: string; label: string }[] = [
    { value: 'all', label: 'All Accounts' },
    { value: 'taxable', label: 'Taxable' },
    { value: 'ira', label: 'Tax-Deferred (IRA)' },
    ...accounts.map((a) => ({
      value: a.account_number,
      label: a.account_name || a.account_number,
    })),
  ];

  return (
    <div style={{ width }} className="min-w-0">
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled}
            className="h-8 w-full min-w-0 justify-between gap-1 px-2.5 font-normal"
            aria-label={`Account filter: ${labelForValue(value, accounts)}`}
          >
            <span className="truncate">{labelForValue(value, accounts)}</span>
            <ChevronDown className="size-4 shrink-0 opacity-60" aria-hidden />
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="start"
            sideOffset={4}
            className={cn(
              'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 max-h-[min(24rem,70vh)] min-w-[var(--radix-dropdown-menu-trigger-width)] overflow-y-auto overflow-x-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md data-[state=closed]:animate-out data-[state=open]:animate-in'
            )}
          >
            {items.map((it) => (
              <DropdownMenu.Item
                key={it.value}
                className={cn(
                  'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
                  'focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
                  it.value === value && 'bg-accent/60'
                )}
                onSelect={() => onChange(it.value)}
              >
                {it.label}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
};

export default CompactAccountSelector;
