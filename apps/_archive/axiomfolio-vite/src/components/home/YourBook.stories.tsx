import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { YourBook } from './YourBook';
import { ColorModeProvider } from '../../theme/colorMode';

export default { title: 'Home/YourBook' };

function Wrap({ children }: { children: React.ReactNode }) {
  const client = React.useMemo(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }), []);
  return (
    <QueryClientProvider client={client}>
      <ColorModeProvider>
        <MemoryRouter>
          <div className="mx-auto max-w-4xl bg-background p-6">{children}</div>
        </MemoryRouter>
      </ColorModeProvider>
    </QueryClientProvider>
  );
}

export const Live = () => (
  <Wrap>
    <YourBook />
  </Wrap>
);
