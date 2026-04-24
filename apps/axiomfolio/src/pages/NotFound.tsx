import * as React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { openCommandPalette } from '@/components/cmdk/openCommandPalette';
import { cn } from '@/lib/utils';

const NotFound: React.FC = () => {
  const location = useLocation();
  const path = location.pathname;

  return (
    <div
      className={cn(
        'flex min-h-[50vh] flex-col items-center justify-center gap-6 bg-background px-4 py-12 text-center'
      )}
    >
      <div className="max-w-md space-y-2">
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground">
          Looks like you wandered off the map
        </h1>
        <p className="text-sm text-muted-foreground">
          Nothing lives at <span className="font-mono text-foreground">{path}</span>. That happens
          when bookmarks age or links go stale — no stress, we will get you back on track.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button asChild>
          <Link to="/">Go home</Link>
        </Button>
        <Button
          type="button"
          variant="outline"
          className="border-border bg-muted/40 hover:bg-muted"
          onClick={() => openCommandPalette()}
        >
          Open Command Palette
        </Button>
      </div>
    </div>
  );
};

export default NotFound;
