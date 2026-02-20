import React from 'react';
import { Box, Button, HStack, Input, Text } from '@chakra-ui/react';
import { FiInbox } from 'react-icons/fi';
import { useColorMode } from '../theme/colorMode';
import AppCard from '../components/ui/AppCard';
import EmptyState from '../components/ui/EmptyState';
import FormField from '../components/ui/FormField';
import StatCard from '../components/shared/StatCard';
import Pagination from '../components/ui/Pagination';
import { Page, PageHeader } from '../components/ui/Page';
import Toolbar from '../components/ui/Toolbar';

export default {
  title: 'DesignSystem/UIPrimitives',
};

export const Overview = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const [page, setPage] = React.useState(1);

  return (
    <Page>
      <PageHeader
        title="UI primitives"
        subtitle={`Mode: ${colorMode}`}
        actions={<Button variant="outline" onClick={toggleColorMode}>Toggle mode</Button>}
      />

      <Box display="flex" flexDirection="column" gap={8}>
        <AppCard>
          <Text fontWeight="semibold" mb={3}>FormField</Text>
          <FormField label="Email" helperText="We’ll never share your email.">
            <Input placeholder="you@example.com" />
          </FormField>
        </AppCard>

        <AppCard>
          <Text fontWeight="semibold" mb={3}>EmptyState</Text>
          <EmptyState
            icon={FiInbox}
            title="No items"
            description="When there’s nothing to show, we keep it calm and actionable."
            action={{ label: 'Create', onClick: () => {} }}
            secondaryAction={{ label: 'Learn more', onClick: () => {} }}
          />
        </AppCard>

        <AppCard>
          <Text fontWeight="semibold" mb={3}>StatCard (full)</Text>
          <Box display="flex" flexDirection="column" gap={3}>
            <StatCard variant="full" label="Tracked Symbols" value={512} helpText="Universe size" />
            <StatCard variant="full" label="Daily Coverage %" value="98.2%" helpText="502 / 511 bars" trend="up" color="green.400" />
            <StatCard variant="full" label="5m Coverage %" value="92.1%" helpText="470 / 511 bars" trend="down" color="red.400" />
          </Box>
        </AppCard>

        <AppCard>
          <Text fontWeight="semibold" mb={3}>Toolbar</Text>
          <Toolbar>
            <HStack gap={2}>
              <Button size="sm" variant="outline">Left</Button>
              <Button size="sm">Right</Button>
            </HStack>
          </Toolbar>
        </AppCard>

        <AppCard>
          <Text fontWeight="semibold" mb={3}>Pagination</Text>
          <Pagination
            page={page}
            pageSize={25}
            total={4585}
            onPageChange={setPage}
            onPageSizeChange={() => {}}
          />
        </AppCard>
      </Box>
    </Page>
  );
};


