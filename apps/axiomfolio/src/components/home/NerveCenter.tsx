/**
 * NerveCenter — up to 5 attention items from `useHomeAttention`.
 *
 * Empty state has personality: "Everything's steady. You earned this moment."
 * We stay quiet when there's nothing to do — no fake urgency.
 */
import * as React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Bell } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/skeleton';
import { useHomeAttention, type AttentionItem, type AttentionTone } from '@/hooks/useHomeAttention';
import { cn } from '@/lib/utils';

const TONE_DOT: Record<AttentionTone, string> = {
  crit: 'bg-[rgb(var(--status-danger)/1)]',
  warn: 'bg-[rgb(var(--status-warning)/1)]',
  ok: 'bg-[rgb(var(--status-success)/1)]',
};

const TONE_LABEL: Record<AttentionTone, string> = {
  crit: 'Critical',
  warn: 'Watch',
  ok: 'Update',
};

function AttentionRow({ item }: { item: AttentionItem }) {
  return (
    <Link
      to={item.href}
      className={cn(
        'group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
        'hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none',
      )}
      aria-label={`${TONE_LABEL[item.tone]}: ${item.title}`}
    >
      <span
        className={cn('inline-block size-2 rounded-full shrink-0', TONE_DOT[item.tone])}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-foreground">{item.title}</div>
        <div className="truncate text-xs text-muted-foreground">{item.subtitle}</div>
      </div>
      <ArrowRight
        className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
    </Link>
  );
}

function NerveCenterInner() {
  const { items, isLoading, isError, isEmpty, refetch } = useHomeAttention();

  return (
    <Card variant="flat">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Bell className="size-4 text-muted-foreground" aria-hidden />
          <span>Nerve center</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            title="Couldn't read your attention feed"
            description="One of the signal hooks failed. Retry when you're ready."
            retry={refetch}
          />
        ) : isEmpty ? (
          <div className="px-2 py-6 text-center">
            <p className="text-sm italic text-muted-foreground">
              Everything's steady. You earned this moment.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {items.map((item) => (
              <AttentionRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export const NerveCenter = React.memo(NerveCenterInner);
export default NerveCenter;
