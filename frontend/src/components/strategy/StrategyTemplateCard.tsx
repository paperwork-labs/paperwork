import React from 'react';
import { TrendingUp, RefreshCw, Target, Zap, type LucideIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { StrategyTemplate } from '../../types/strategy';

interface Props {
  template: StrategyTemplate;
  onUseTemplate: (templateId: string) => void;
}

const TYPE_CONFIG: Record<string, { badgeClass: string; icon: LucideIcon }> = {
  momentum: {
    badgeClass: 'border-blue-500/40 bg-blue-500/10 text-blue-900 dark:text-blue-200',
    icon: TrendingUp,
  },
  mean_reversion: {
    badgeClass: 'border-violet-500/40 bg-violet-500/10 text-violet-900 dark:text-violet-200',
    icon: RefreshCw,
  },
  breakout: {
    badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200',
    icon: Zap,
  },
  custom: {
    badgeClass: 'bg-secondary text-secondary-foreground',
    icon: Target,
  },
};

function formatStrategyType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function StrategyTemplateCard({ template, onUseTemplate }: Props) {
  const config = TYPE_CONFIG[template.strategy_type] ?? {
    badgeClass: 'bg-secondary text-secondary-foreground',
    icon: Target,
  };
  const TypeIcon = config.icon;

  return (
    <Card
      className="cursor-pointer transition-colors hover:ring-foreground/20"
      onClick={() => onUseTemplate(template.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onUseTemplate(template.id);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <CardContent className="flex flex-col gap-3 pt-6">
        <Badge variant="outline" className={cn('w-fit gap-1 pr-2', config.badgeClass)}>
          <TypeIcon className="size-3" aria-hidden />
          {formatStrategyType(template.strategy_type)}
        </Badge>

        <p className="font-semibold text-foreground">{template.name}</p>

        <p className="line-clamp-3 text-sm text-muted-foreground">{template.description}</p>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{template.position_size_pct}% position</span>
          <span>{template.max_positions} max positions</span>
          {template.stop_loss_pct != null && <span>{template.stop_loss_pct}% stop loss</span>}
        </div>

        <Button
          type="button"
          size="sm"
          className="w-fit"
          onClick={(e) => {
            e.stopPropagation();
            onUseTemplate(template.id);
          }}
        >
          Use Template
        </Button>
      </CardContent>
    </Card>
  );
}
