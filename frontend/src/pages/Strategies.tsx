import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Text, SimpleGrid, CardRoot, CardBody, Badge, HStack, VStack,
  Button, Icon, Input, DialogRoot, DialogBackdrop, DialogPositioner,
  DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter,
  DialogCloseTrigger,
} from '@chakra-ui/react';
import { FiPlus, FiPlay, FiPause, FiClock } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { Page, PageHeader } from '../components/ui/Page';
import EmptyState from '../components/ui/EmptyState';
import StrategyTemplateCard from '../components/strategy/StrategyTemplateCard';
import api from '../services/api';
import type { Strategy, StrategyStatus, StrategyTemplate } from '../types/strategy';

function extractData<T>(resp: { data?: { data?: T } }): T {
  return (resp?.data as { data?: T })?.data ?? resp?.data as T;
}

const STATUS_CONFIG: Record<StrategyStatus, { color: string; icon: typeof FiPlay }> = {
  active: { color: 'green', icon: FiPlay },
  paused: { color: 'yellow', icon: FiPause },
  draft: { color: 'gray', icon: FiClock },
  stopped: { color: 'red', icon: FiClock },
  archived: { color: 'red', icon: FiClock },
};

function StrategyCard({
  strategy,
  onClick,
}: {
  strategy: Strategy;
  onClick: () => void;
}) {
  const cfg = STATUS_CONFIG[strategy.status] ?? STATUS_CONFIG.draft;

  return (
    <CardRoot
      bg="bg.card"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      cursor="pointer"
      transition="border-color 0.2s"
      _hover={{ borderColor: 'border.emphasized' }}
      onClick={onClick}
    >
      <CardBody>
        <VStack align="stretch" gap={3}>
          <HStack justify="space-between">
            <Text fontWeight="semibold" fontSize="md" color="fg.default">
              {strategy.name}
            </Text>
            <Badge colorPalette={cfg.color} variant="subtle" size="sm">
              <Icon as={cfg.icon} mr={1} />
              {strategy.status}
            </Badge>
          </HStack>
          {strategy.description && (
            <Text fontSize="sm" color="fg.muted" lineClamp={2}>
              {strategy.description}
            </Text>
          )}
          <HStack gap={3} fontSize="xs" color="fg.muted">
            <Text>Type: {strategy.strategy_type}</Text>
            <Text>Created: {new Date(strategy.created_at).toLocaleDateString()}</Text>
          </HStack>
        </VStack>
      </CardBody>
    </CardRoot>
  );
}

const Strategies: React.FC = () => {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'custom' | 'template'>('custom');
  const [selectedTemplate, setSelectedTemplate] = useState<StrategyTemplate | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetchStrategies = useCallback(async () => {
    try {
      const resp = await api.get('/strategies');
      setStrategies(extractData<Strategy[]>(resp) ?? []);
    } catch {
      setStrategies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const resp = await api.get('/strategies/templates');
      setTemplates(extractData<StrategyTemplate[]>(resp) ?? []);
    } catch {
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const openCustomDialog = () => {
    setDialogMode('custom');
    setSelectedTemplate(null);
    setFormName('');
    setFormDescription('');
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openTemplateDialog = (template: StrategyTemplate) => {
    setDialogMode('template');
    setSelectedTemplate(template);
    setFormName(template.name);
    setFormDescription(template.description ?? '');
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleUseTemplate = (templateId: string) => {
    const template = templates.find((t) => t.id === templateId);
    if (template) {
      openTemplateDialog(template);
    }
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setSelectedTemplate(null);
    setFormName('');
    setFormDescription('');
    setSubmitError(null);
  };

  const handleSubmit = async () => {
    const trimmedName = formName.trim();
    if (!trimmedName) {
      setSubmitError('Name is required');
      return;
    }

    setSubmitLoading(true);
    setSubmitError(null);

    try {
      if (dialogMode === 'template' && selectedTemplate) {
        const resp = await api.post('/strategies/from-template', {
          template_id: selectedTemplate.id,
          name: trimmedName,
          description: formDescription.trim() || undefined,
          overrides: {},
        });
        const created = extractData<Strategy>(resp);
        if (created?.id) {
          closeDialog();
          navigate(`/strategies/${created.id}`);
        }
      } else {
        const resp = await api.post('/strategies', {
          name: trimmedName,
          description: formDescription.trim() || undefined,
          strategy_type: 'custom',
          config: {},
        });
        const created = extractData<Strategy>(resp);
        if (created?.id) {
          closeDialog();
          navigate(`/strategies/${created.id}`);
        }
      }
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setSubmitError(e?.response?.data?.detail ?? e?.message ?? 'Failed to create strategy');
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <Page>
      <PageHeader
        title="Strategies"
        subtitle="Quantitative strategy engine — define rules, backtest, and deploy"
        actions={
          <Button size="sm" colorPalette="blue" onClick={openCustomDialog}>
            <Icon as={FiPlus} mr={1} /> New Strategy
          </Button>
        }
      />

      {loading ? (
        <Text color="fg.muted">Loading strategies...</Text>
      ) : strategies.length === 0 ? (
        <EmptyState
          title="No strategies yet"
          description="Create your first strategy to automate trading decisions based on market indicators and rules."
        />
      ) : (
        <Box mb={10}>
          <Text fontWeight="semibold" color="fg.default" mb={4}>
            My Strategies
          </Text>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
            {strategies.map((s) => (
              <StrategyCard
                key={s.id}
                strategy={s}
                onClick={() => navigate(`/strategies/${s.id}`)}
              />
            ))}
          </SimpleGrid>
        </Box>
      )}

      <Box>
        <Text fontWeight="semibold" color="fg.default" mb={4}>
          Strategy Templates
        </Text>
        {templatesLoading ? (
          <Text color="fg.muted">Loading templates...</Text>
        ) : (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
            {templates.map((tpl) => (
              <StrategyTemplateCard
                key={tpl.id}
                template={tpl}
                onUseTemplate={handleUseTemplate}
              />
            ))}
          </SimpleGrid>
        )}
      </Box>

      <DialogRoot open={dialogOpen} onOpenChange={(d) => { if (!d.open) closeDialog(); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="md">
            <DialogHeader>
              <DialogTitle>
                {dialogMode === 'template' ? 'Create from Template' : 'New Strategy'}
              </DialogTitle>
            </DialogHeader>
            <DialogBody>
              <VStack align="stretch" gap={4}>
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="fg.default" mb={2}>
                    Name
                  </Text>
                  <Input
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="Strategy name"
                  />
                </Box>
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="fg.default" mb={2}>
                    Description (optional)
                  </Text>
                  <Input
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                    placeholder="Brief description"
                  />
                </Box>
                {submitError && (
                  <Text fontSize="sm" color="red.500">
                    {submitError}
                  </Text>
                )}
              </VStack>
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={closeDialog}>
                Cancel
              </Button>
              <Button
                colorPalette="blue"
                onClick={handleSubmit}
                loading={submitLoading}
                disabled={submitLoading}
              >
                Create
              </Button>
            </DialogFooter>
            <DialogCloseTrigger />
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Page>
  );
};

export default Strategies;
