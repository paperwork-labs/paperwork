import React from 'react';
import { Box, Text, Button } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/ui/Page';
import AppCard from '../components/ui/AppCard';

const SettingsNotifications: React.FC = () => {
  const navigate = useNavigate();
  return (
    <Box w="full" maxW="960px" mx="auto">
      <PageHeader title="Notifications" subtitle="Notification preferences and delivery channels." />
      <AppCard mt={6}>
        <Text color="fg.muted" fontSize="sm" mb={3}>
          Notification configuration is being migrated to Chakra v3. The current notifications center still lives outside Settings.
        </Text>
        <Button size="sm" variant="outline" onClick={() => navigate('/notifications')}>
          Open Notifications Center
        </Button>
      </AppCard>
    </Box>
  );
};

export default SettingsNotifications;


