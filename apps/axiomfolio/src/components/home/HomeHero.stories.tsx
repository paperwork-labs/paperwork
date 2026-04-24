import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { HomeHero } from './HomeHero';
import { ColorModeProvider } from '../../theme/colorMode';

export default { title: 'Home/HomeHero' };

function Wrap({ children }: { children: React.ReactNode }) {
  const client = React.useMemo(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }), []);
  return (
    <QueryClientProvider client={client}>
      <ColorModeProvider>
        <MemoryRouter>
          <div className="mx-auto max-w-5xl bg-background p-6">{children}</div>
        </MemoryRouter>
      </ColorModeProvider>
    </QueryClientProvider>
  );
}

export const Loading = () => (
  <Wrap>
    <HomeHero hasBrokers brokersLoading />
  </Wrap>
);

export const NoBrokers = () => (
  <Wrap>
    <HomeHero hasBrokers={false} />
  </Wrap>
);

export const BrokersError = () => (
  <Wrap>
    <HomeHero hasBrokers brokersError={new Error('Could not reach broker service')} />
  </Wrap>
);

export const DataLive = () => (
  <Wrap>
    <HomeHero hasBrokers />
  </Wrap>
);
