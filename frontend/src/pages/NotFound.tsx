import * as React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';

const NotFound: React.FC = () => {
  const location = useLocation();
  const path = location.pathname;

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="space-y-2">
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-foreground">
          Page not found
        </h1>
        <p className="text-sm text-muted-foreground">
          No page matches <span className="font-mono text-foreground">{path}</span>
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button asChild>
          <Link to="/">Home</Link>
        </Button>
        <Link
          to="/pricing"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          Pricing
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
