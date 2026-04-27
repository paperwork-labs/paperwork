import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Link2 } from 'lucide-react';

export interface FirstRunHeroProps {
  onEngage?: () => void;
}

export function FirstRunHero({ onEngage }: FirstRunHeroProps) {
  return (
    <Card className="border-border bg-muted/40 shadow-xs">
      <CardContent className="flex flex-col gap-4 p-6">
        <div className="flex flex-row items-center gap-3">
          <div className="rounded-md bg-muted p-2">
            <Link2 className="size-6 text-foreground" aria-hidden />
          </div>
          <h2 className="text-xl font-semibold text-foreground">Connect your first brokerage to get started</h2>
        </div>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
          <li>
            <span className="text-foreground">Choose a broker</span> from the grid below.
          </li>
          <li>
            <span className="text-foreground">Authorize</span> when prompted (OAuth popup or credentials in the connection
            dialog).
          </li>
          <li>
            <span className="text-foreground">Sync runs automatically</span> after the link succeeds; you can also run a
            full sync from this page once connected.
          </li>
        </ol>
        <Button
          type="button"
          className="self-start"
          onClick={() => {
            onEngage?.();
            document.getElementById('broker-picker-grid')?.scrollIntoView({ behavior: 'smooth' });
          }}
        >
          Choose a broker
        </Button>
      </CardContent>
    </Card>
  );
}
