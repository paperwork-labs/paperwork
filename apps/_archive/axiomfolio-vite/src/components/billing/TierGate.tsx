/**
 * TierGate — render children only if the current user's tier unlocks the
 * requested feature, otherwise render an upgrade prompt.
 *
 * Usage:
 *
 *   <TierGate feature="brain.native_chat">
 *     <AgentBrainChatPanel />
 *   </TierGate>
 *
 * Custom fallback:
 *
 *   <TierGate feature="brain.native_chat" fallback={<MarketingTeaser />}>
 *     <AgentBrainChatPanel />
 *   </TierGate>
 *
 * Why a component and not a render-prop:
 * - Keeps call sites declarative and easy to grep for tier-gated regions.
 * - Centralizes the upgrade prompt so we can A/B test copy in one place.
 *
 * Why not gate at the route level only:
 * - Many features are sub-views inside an otherwise-allowed route (e.g. an
 *   "Ask the Brain" panel inside the dashboard a Free user can still see).
 * - Backend `require_feature` still enforces the actual data contract; this
 *   component is purely about visual disclosure.
 */

import React from 'react';
import { HelpCircle, Lock } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

import useEntitlement from '@/hooks/useEntitlement';
import { TIER_LABEL, type SubscriptionTier } from '@/types/entitlement';

interface TierGateProps {
  /** Feature key from `feature_catalog.py` (e.g. `brain.native_chat`). */
  feature: string;
  /** Children rendered only when access is granted. */
  children: React.ReactNode;
  /** Optional override for the locked-state UI. */
  fallback?: React.ReactNode;
  /** Optional override for the loading-state UI. Defaults to `null` so most
   *  gates simply render nothing while the entitlement is fetched. */
  loadingFallback?: React.ReactNode;
  /** Called when the user clicks the upgrade button on the default fallback. */
  onUpgradeClick?: (requiredTier: SubscriptionTier) => void;
  /** Optional short explanation (e.g. pass-through costs) shown next to the upgrade CTA. */
  costJustification?: string;
}

const TierGate: React.FC<TierGateProps> = ({
  feature,
  children,
  fallback,
  loadingFallback = null,
  onUpgradeClick,
  costJustification,
}) => {
  const { can, requireTier, isLoading, isError } = useEntitlement();

  if (isLoading) {
    return <>{loadingFallback}</>;
  }

  // Fail closed: if the entitlement endpoint errored, hide gated UI rather
  // than render-and-pray. The backend still enforces the actual data; this
  // is just visual hygiene.
  if (isError) {
    return <>{fallback ?? null}</>;
  }

  if (can(feature)) {
    return <>{children}</>;
  }

  if (fallback !== undefined) {
    return <>{fallback}</>;
  }

  return (
    <DefaultUpgradePrompt
      feature={feature}
      requiredTier={requireTier(feature)}
      onUpgradeClick={onUpgradeClick}
      costJustification={costJustification}
    />
  );
};

interface DefaultUpgradePromptProps {
  feature: string;
  requiredTier: SubscriptionTier | null;
  onUpgradeClick?: (requiredTier: SubscriptionTier) => void;
  costJustification?: string;
}

const DefaultUpgradePrompt: React.FC<DefaultUpgradePromptProps> = ({
  feature,
  requiredTier,
  onUpgradeClick,
  costJustification,
}) => {
  const tierLabel = requiredTier ? TIER_LABEL[requiredTier] : 'a paid plan';

  const upgradeRow =
    requiredTier !== null ? (
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button type="button" size="sm" onClick={() => onUpgradeClick?.(requiredTier)}>
          Upgrade to {TIER_LABEL[requiredTier]}
        </Button>
        {costJustification ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex size-8 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Why this plan has a price"
              >
                <HelpCircle className="size-4" aria-hidden />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-left text-xs leading-snug">{costJustification}</TooltipContent>
          </Tooltip>
        ) : null}
      </div>
    ) : null;

  return (
    <TooltipProvider delayDuration={200}>
      <Card className="border-dashed bg-muted/30" data-testid={`tier-gate-locked-${feature}`}>
        <CardContent className="flex flex-col items-center gap-3 px-6 py-8 text-center">
          <Lock className="size-6 text-muted-foreground" aria-hidden />
          <Badge variant="outline" className="text-xs uppercase tracking-wide">
            {tierLabel} feature
          </Badge>
          <p className="max-w-md text-sm text-muted-foreground">
            This is a {tierLabel} feature. Upgrade your plan to unlock it.
          </p>
          {upgradeRow}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

export default TierGate;
