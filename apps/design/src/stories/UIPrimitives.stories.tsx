import React from 'react';
import { Inbox } from 'lucide-react';
import { useColorMode } from '@axiomfolio/theme/colorMode';
import AppCard from '@axiomfolio/components/ui/AppCard';
import EmptyState from '@axiomfolio/components/ui/EmptyState';
import FormField from '@axiomfolio/components/ui/FormField';
import StatCard from '@axiomfolio/components/shared/StatCard';
import Pagination from '@axiomfolio/components/ui/Pagination';
import { Page, PageHeader } from '@axiomfolio/components/ui/Page';
import Toolbar from '@axiomfolio/components/ui/Toolbar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: 'DesignSystem/UIPrimitives',
};
export default meta;

type Story = StoryObj;

export const Overview: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const [page, setPage] = React.useState(1);

  return (
    <Page>
      <PageHeader
        title="UI primitives"
        subtitle={`Mode: ${colorMode}`}
        actions={
          <Button type="button" variant="outline" onClick={toggleColorMode}>
            Toggle mode
          </Button>
        }
      />

      <div className="flex flex-col gap-8">
        <AppCard>
          <div className="mb-3 font-semibold">FormField</div>
          <FormField label="Email" helperText="We’ll never share your email.">
            <Input placeholder="you@example.com" />
          </FormField>
        </AppCard>

        <AppCard>
          <div className="mb-3 font-semibold">EmptyState</div>
          <EmptyState
            icon={Inbox}
            title="No items"
            description="When there’s nothing to show, we keep it calm and actionable."
            action={{ label: 'Create', onClick: () => {} }}
            secondaryAction={{ label: 'Learn more', onClick: () => {} }}
          />
        </AppCard>

        <AppCard>
          <div className="mb-3 font-semibold">StatCard (full)</div>
          <div className="flex flex-col gap-3">
            <StatCard variant="full" label="Tracked Symbols" value={512} helpText="Universe size" />
            <StatCard variant="full" label="Daily Coverage %" value="98.2%" helpText="502 / 511 bars" trend="up" color="green.400" />
            <StatCard variant="full" label="5m Coverage %" value="92.1%" helpText="470 / 511 bars" trend="down" color="red.400" />
          </div>
        </AppCard>

        <AppCard>
          <div className="mb-3 font-semibold">Toolbar</div>
          <Toolbar>
            <div className="flex flex-row gap-2">
              <Button type="button" size="sm" variant="outline">
                Left
              </Button>
              <Button type="button" size="sm">
                Right
              </Button>
            </div>
          </Toolbar>
        </AppCard>

        <AppCard>
          <div className="mb-3 font-semibold">Pagination</div>
          <Pagination
            page={page}
            pageSize={25}
            total={4585}
            onPageChange={setPage}
            onPageSizeChange={() => {}}
          />
        </AppCard>
      </div>
    </Page>
  );
},
};
