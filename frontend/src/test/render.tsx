import React from 'react';
import type { PropsWithChildren, ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';

import { ColorModeProvider } from '../theme/colorMode';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

export { createTestQueryClient };

export type RenderWithProvidersOptions = {
  route?: string;
};

function Providers({ children, route = '/', queryClient }: PropsWithChildren<{ route?: string; queryClient?: QueryClient }>) {
  const client = queryClient ?? createTestQueryClient();
  return (
    <QueryClientProvider client={client}>
      <ColorModeProvider>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </ColorModeProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}) {
  const queryClient = createTestQueryClient();
  return render(<Providers route={options.route} queryClient={queryClient}>{ui}</Providers>);
}


