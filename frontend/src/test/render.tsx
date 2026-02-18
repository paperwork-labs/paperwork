import React from 'react';
import type { PropsWithChildren, ReactElement } from 'react';
import { ChakraProvider } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';

import { system } from '../theme/system';
import { ColorModeProvider } from '../theme/colorMode';

export type RenderWithProvidersOptions = {
  route?: string;
};

function Providers({ children, route = '/' }: PropsWithChildren<{ route?: string }>) {
  return (
    <ChakraProvider value={system}>
      <ColorModeProvider>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </ColorModeProvider>
    </ChakraProvider>
  );
}

export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}) {
  return render(<Providers route={options.route}>{ui}</Providers>);
}


