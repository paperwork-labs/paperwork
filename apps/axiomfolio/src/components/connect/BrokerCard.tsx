/**
 * BrokerCard — single tile in the Connect hub grid.
 *
 * The card is intentionally a "pure" view component: it accepts a
 * `ConnectionBrokerOption` and a couple of click handlers, and renders
 * the right CTA based on the catalog `status` + `method`. All of the
 * "where does Connect actually go?" routing is delegated to the parent
 * page via callback so we keep the per-broker OAuth knowledge in one
 * place (`ConnectAccounts.tsx`).
 *
 * Per D106 / 3l-iii: import-only brokers carry an inline transparency
 * tooltip explaining *why* it isn't OAuth — Fidelity et al. don't expose
 * APIs to retail. That microcopy is part of the trust contract.
 */
import * as React from "react";
import Link from "next/link";
import { CheckCircle2, ChevronRight, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import { RichTooltip } from "@/components/ui/RichTooltip";
import { cn } from "@/lib/utils";
import type { ConnectionBrokerOption } from "@/services/api";

import { BrokerLogo } from "./BrokerLogo";

interface BrokerCardProps {
  broker: ConnectionBrokerOption;
  onConnectOAuth: (broker: ConnectionBrokerOption) => void;
  onImport: (broker: ConnectionBrokerOption) => void;
  onNotifyMe: (broker: ConnectionBrokerOption) => void;
  onManage: (broker: ConnectionBrokerOption) => void;
  onSnaptradePricing: (broker: ConnectionBrokerOption) => void;
}

function formatLastSync(iso: string | null): string {
  if (!iso) return "Not synced yet";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "Not synced yet";
  const diffMs = Date.now() - dt.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60_000));
  if (minutes < 1) return "Synced just now";
  if (minutes < 60) return `Synced ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Synced ${hours} hr ago`;
  const days = Math.round(hours / 24);
  return `Synced ${days} day${days === 1 ? "" : "s"} ago`;
}

function ConnectedBadge() {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5",
        "text-[11px] font-medium text-emerald-700 dark:text-emerald-300",
      )}
    >
      <CheckCircle2 className="size-3" aria-hidden />
      Connected
    </span>
  );
}

function WhyNotOAuth({ brokerName }: { brokerName: string }) {
  return (
    <RichTooltip
      ariaLabel={`Why ${brokerName} uses CSV import`}
      side="top"
      maxWidth={300}
      trigger={
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1 text-[11px] text-muted-foreground",
            "underline-offset-4 hover:text-foreground hover:underline",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded",
          )}
          aria-label={`Why is ${brokerName} CSV-only?`}
        >
          <Info className="size-3" aria-hidden />
          Why CSV?
        </button>
      }
    >
      <div className="space-y-2 p-3 text-xs">
        <p className="font-medium text-foreground">No API for retail</p>
        <p className="text-muted-foreground">
          {brokerName} doesn&apos;t expose an API to retail customers. Two options:
          import your CSV/statement here for free, or a paid tier&apos;s one-click
          via SnapTrade pass-through — we don&apos;t mark it up.
        </p>
        <Link
          href="/why-free"
          className="inline-flex text-foreground underline underline-offset-4"
        >
          Read more
        </Link>
      </div>
    </RichTooltip>
  );
}

function CTASlot({
  broker,
  onConnectOAuth,
  onImport,
  onNotifyMe,
  onManage,
  onSnaptradePricing,
}: BrokerCardProps) {
  const { method, status, user_state } = broker;

  if (user_state.connected) {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onManage(broker)}
        aria-label={`Manage ${broker.name} connection`}
      >
        Manage
        <ChevronRight aria-hidden />
      </Button>
    );
  }

  if (status === "available" && method === "oauth") {
    return (
      <Button
        type="button"
        size="sm"
        onClick={() => onConnectOAuth(broker)}
        className={cn(
          "bg-emerald-600 text-white hover:bg-emerald-600/90",
          "focus-visible:ring-emerald-600/40",
        )}
        aria-label={`Connect ${broker.name} via OAuth`}
      >
        Connect
      </Button>
    );
  }

  if (status === "available" && method === "import") {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onImport(broker)}
        aria-label={`Import ${broker.name} via CSV`}
      >
        Import
      </Button>
    );
  }

  if (status === "coming_v1_1") {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onNotifyMe(broker)}
        aria-label={`Notify me when ${broker.name} ships`}
      >
        Notify me
      </Button>
    );
  }

  if (status === "coming_v1_2_snaptrade") {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onSnaptradePricing(broker)}
        aria-label={`${broker.name} available on Pro — view pricing`}
      >
        Available on Pro
        <ChevronRight aria-hidden />
      </Button>
    );
  }

  return null;
}

export function BrokerCard(props: BrokerCardProps) {
  const { broker } = props;
  const isImport = broker.method === "import" && broker.status === "available";

  return (
    <ChartGlassCard
      level="resting"
      interactive
      padding="md"
      as="article"
      ariaLabel={`${broker.name} connection card`}
      className="h-full"
    >
      <div className="flex h-full flex-col gap-4">
        <div className="flex items-start gap-3">
          <BrokerLogo
            slug={broker.slug}
            name={broker.name}
            remoteLogoUrl={broker.logo_url}
            size={40}
            className="h-10 w-10 p-0.5"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <h3 className="truncate font-heading text-sm font-medium text-foreground">
                {broker.name}
              </h3>
              {broker.user_state.connected ? <ConnectedBadge /> : null}
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {broker.description}
            </p>
          </div>
        </div>

        <div className="mt-auto flex items-end justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            {broker.user_state.connected ? (
              <p className="truncate text-[11px] text-muted-foreground">
                {formatLastSync(broker.user_state.last_synced_at)}
                {broker.user_state.account_count > 1
                  ? ` · ${broker.user_state.account_count} accounts`
                  : ""}
              </p>
            ) : null}
            {!broker.user_state.connected && isImport ? (
              <WhyNotOAuth brokerName={broker.name} />
            ) : null}
            {!broker.user_state.connected && broker.status === "coming_v1_2_snaptrade" ? (
              <Badge variant="outline" className="text-[10px]">
                v1.2 · Pro
              </Badge>
            ) : null}
            {!broker.user_state.connected && broker.status === "coming_v1_1" ? (
              <Badge variant="secondary" className="text-[10px]">
                Coming in v1.1
              </Badge>
            ) : null}
          </div>
          <CTASlot {...props} />
        </div>
      </div>
    </ChartGlassCard>
  );
}

export default BrokerCard;
