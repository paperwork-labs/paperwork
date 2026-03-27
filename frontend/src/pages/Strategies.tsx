import React, { useEffect, useState, useCallback } from 'react';
import { Clock, Loader2, Pause, Play, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Page, PageHeader } from '../components/ui/Page';
import EmptyState from '../components/ui/EmptyState';
import StrategyTemplateCard from '../components/strategy/StrategyTemplateCard';
import { BacktestStatusBadge } from '../components/strategy/BacktestStatusBadge';
import api from '../services/api';
import { formatDateFriendly } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import type { Strategy, StrategyStatus, StrategyTemplate } from '../types/strategy';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function extractData<T>(resp: { data?: { data?: T } }): T {
  return (resp?.data as { data?: T })?.data ?? (resp?.data as T);
}

const STATUS_CONFIG: Record<
  StrategyStatus,
  { className: string; Icon: typeof Play }
> = {
  active: {
    className: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
    Icon: Play,
  },
  paused: {
    className: 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
    Icon: Pause,
  },
  draft: {
    className: 'border-border bg-muted/60 text-muted-foreground',
    Icon: Clock,
  },
  stopped: {
    className: 'border-destructive/40 bg-destructive/10 text-destructive',
    Icon: Clock,
  },
  archived: {
    className: 'border-destructive/40 bg-destructive/10 text-destructive',
    Icon: Clock,
  },
};

function StrategyCard({
  strategy,
  onClick,
  timezone,
}: {
  strategy: Strategy;
  onClick: () => void;
  timezone?: string;
}) {
  const cfg = STATUS_CONFIG[strategy.status] ?? STATUS_CONFIG.draft;
  const Icon = cfg.Icon;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className="cursor-pointer gap-0 border border-border py-4 shadow-none ring-0 transition-colors hover:border-primary/40"
    >
      <CardContent className="flex flex-col gap-3 px-5 py-0">
        <div className="flex items-start justify-between gap-2">
          <p className="font-medium text-foreground">{strategy.name}</p>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
            <BacktestStatusBadge validation={strategy.backtest_validation} stopRowClick />
            <Badge variant="outline" className={cn('h-5 gap-1 text-[10px] font-medium', cfg.className)}>
              <Icon className="size-3" aria-hidden />
              {strategy.status}
            </Badge>
          </div>
        </div>
        {strategy.description ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{strategy.description}</p>
        ) : null}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>Type: {strategy.strategy_type}</span>
          <span>Created: {formatDateFriendly(strategy.created_at, timezone)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

const Strategies: React.FC = () => {
  const navigate = useNavigate();
  const { timezone } = useUserPreferences();
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
          navigate(`/market/strategies/${created.id}`);
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
          navigate(`/market/strategies/${created.id}`);
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
          <Button size="sm" onClick={openCustomDialog} className="gap-1">
            <Plus className="size-4" aria-hidden />
            New Strategy
          </Button>
        }
      />

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading strategies...</p>
      ) : strategies.length === 0 ? (
        <EmptyState
          title="No strategies yet"
          description="Create your first strategy to automate trading decisions based on market indicators and rules."
        />
      ) : (
        <div className="mb-10">
          <p className="mb-4 font-semibold text-foreground">My Strategies</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {strategies.map((s) => (
              <StrategyCard
                key={s.id}
                strategy={s}
                onClick={() => navigate(`/market/strategies/${s.id}`)}
                timezone={timezone}
              />
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="mb-4 font-semibold text-foreground">Strategy Templates</p>
        {templatesLoading ? (
          <p className="text-sm text-muted-foreground">Loading templates...</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {templates.map((tpl) => (
              <StrategyTemplateCard key={tpl.id} template={tpl} onUseTemplate={handleUseTemplate} />
            ))}
          </div>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{dialogMode === 'template' ? 'Create from Template' : 'New Strategy'}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div>
              <p className="mb-2 text-sm font-medium text-foreground">Name</p>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Strategy name"
              />
            </div>
            <div>
              <p className="mb-2 text-sm font-medium text-foreground">Description (optional)</p>
              <Input
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Brief description"
              />
            </div>
            {submitError ? <p className="text-sm text-destructive">{submitError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitLoading} className="gap-2">
              {submitLoading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  );
};

export default Strategies;
