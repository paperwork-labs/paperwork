import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  AlertRoot,
  AlertIndicator,
  AlertTitle,
  AlertDescription,
  Button,
  VStack,
  Text,
  Code,
} from '@chakra-ui/react';

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
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    this.setState({
      error,
      errorInfo,
    });

    // Call optional error reporting callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Report to error tracking service (e.g., Sentry)
    // TODO: Add error tracking integration
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
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return <ErrorFallback
        error={this.state.error}
        errorInfo={this.state.errorInfo}
        onRetry={this.handleRetry}
        onReload={this.handleReload}
      />;
    }

    return this.props.children;
  }
}

// Error fallback component
const ErrorFallback: React.FC<{
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onRetry: () => void;
  onReload: () => void;
}> = ({ error, errorInfo, onRetry, onReload }) => {
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const bgColor = 'bg.card';
  const borderColor = 'border.subtle';

  return (
    <Box
      p={8}
      maxW="container.md"
      mx="auto"
      bg={bgColor}
      borderRadius="lg"
      border="1px"
      borderColor={borderColor}
      shadow="lg"
    >
      <AlertRoot status="error" borderRadius="md" mb={6}>
        <AlertIndicator />
        <Box>
          <AlertTitle>Something went wrong!</AlertTitle>
          <AlertDescription>
            An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.
          </AlertDescription>
        </Box>
      </AlertRoot>

      <VStack gap={4} align="stretch">
        <Box>
          <Button colorScheme="blue" onClick={onRetry} mr={3}>
            Try Again
          </Button>
          <Button variant="outline" onClick={onReload}>
            Reload Page
          </Button>
        </Box>

        {error && (
          <Box>
            <Button size="sm" variant="ghost" onClick={() => setDetailsOpen((v) => !v)}>
              {detailsOpen ? 'Hide' : 'Show'} Error Details
            </Button>

            {detailsOpen ? (
              <Box mt={4} p={4} bg="bg.muted" borderRadius="md" borderWidth="1px" borderColor="border.subtle">
                <Text fontWeight="bold" mb={2}>Error Message:</Text>
                <Code display="block" p={2} mb={4} whiteSpace="pre-wrap">
                  {error.message}
                </Code>

                {error.stack ? (
                  <>
                    <Text fontWeight="bold" mb={2}>Stack Trace:</Text>
                    <Code
                      display="block"
                      p={2}
                      whiteSpace="pre-wrap"
                      fontSize="xs"
                      maxH="200px"
                      overflowY="auto"
                    >
                      {error.stack}
                    </Code>
                  </>
                ) : null}
              </Box>
            ) : null}
          </Box>
        )}

        <Text fontSize="sm" color="fg.muted" textAlign="center">
          If this error persists, please{' '}
          <Text as="span" color="blue.500" cursor="pointer" textDecoration="underline">
            report it to our support team
          </Text>
        </Text>
      </VStack>
    </Box>
  );
};

// Higher-order component for wrapping components with error boundary
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  fallback?: ReactNode
) => {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary fallback={fallback}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
};

export default ErrorBoundary; 