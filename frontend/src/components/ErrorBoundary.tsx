import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo,
    });

    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  private handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback error={this.state.error} onRetry={this.handleRetry} onReload={this.handleReload} />
      );
    }

    return this.props.children;
  }
}

const ErrorFallback: React.FC<{
  error: Error | null;
  onRetry: () => void;
  onReload: () => void;
}> = ({ error, onRetry, onReload }) => {
  const [detailsOpen, setDetailsOpen] = React.useState(false);

  return (
    <Card className="mx-auto my-8 max-w-2xl shadow-lg">
      <CardContent className="space-y-6 pt-8">
        <Alert variant="destructive">
          <AlertCircle className="size-4" aria-hidden />
          <AlertTitle>Something went wrong!</AlertTitle>
          <AlertDescription>
            An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.
          </AlertDescription>
        </Alert>

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={onRetry}>
            Try Again
          </Button>
          <Button type="button" variant="outline" onClick={onReload}>
            Reload Page
          </Button>
        </div>

        {error && (
          <div>
            <Button type="button" size="sm" variant="ghost" onClick={() => setDetailsOpen((v) => !v)}>
              {detailsOpen ? 'Hide' : 'Show'} Error Details
            </Button>

            {detailsOpen ? (
              <div className="mt-4 rounded-md border border-border bg-muted/50 p-4">
                <p className="mb-2 font-bold">Error Message:</p>
                <pre className="mb-4 overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-background p-2 text-xs">
                  {error.message}
                </pre>

                {error.stack ? (
                  <>
                    <p className="mb-2 font-bold">Stack Trace:</p>
                    <pre className="max-h-[200px] overflow-auto overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-background p-2 text-xs">
                      {error.stack}
                    </pre>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        )}

        <p className="text-center text-sm text-muted-foreground">
          If this error persists, please report it to our support team.
        </p>
      </CardContent>
    </Card>
  );
};

export const withErrorBoundary = <P extends object>(Component: React.ComponentType<P>, fallback?: ReactNode) => {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary fallback={fallback}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
};

export default ErrorBoundary;
