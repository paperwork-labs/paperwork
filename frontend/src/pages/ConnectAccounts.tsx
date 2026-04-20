/**
 * ConnectAccounts (`/connect`) — unified hub for adding broker connections.
 *
 * Replaces the old "where do I add my account?" confusion. Surfaces every
 * broker we know about with the right CTA per the catalog
 * (`backend/services/portfolio/broker_catalog.py`):
 *   - oauth + available    → green "Connect" → existing OAuth flow
 *   - import + available   → "Import" → /portfolio/import?broker=<slug>
 *   - oauth + coming_v1_1  → "Notify me" → captures email
 *   - oauth + coming_v1_2_lite → "Available on Lite" → /pricing
 *
 * The grid is filterable via two `<SegmentedPeriodSelector>` controls
 * (category + connection method). Loading uses skeletons; error and
 * empty are explicit per the no-silent-fallback rule.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { Page, PageHeader } from "@/components/ui/Page";
import { SegmentedPeriodSelector } from "@/components/ui/SegmentedPeriodSelector";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  connectHubApi,
  type ConnectionBrokerOption,
} from "@/services/api";

import BrokerCard from "@/components/connect/BrokerCard";
import NotifyMeDialog from "@/components/connect/NotifyMeDialog";

type CategoryFilter = "all" | "stocks" | "crypto" | "retirement";
type MethodFilter = "all" | "oauth" | "import" | "coming";

const CATEGORY_OPTIONS = [
  { value: "all", label: "All" },
  { value: "stocks", label: "Stocks" },
  { value: "crypto", label: "Crypto" },
  { value: "retirement", label: "Retirement" },
] as const;

const METHOD_OPTIONS = [
  { value: "all", label: "All" },
  { value: "oauth", label: "OAuth" },
  { value: "import", label: "Import" },
  { value: "coming", label: "Coming" },
] as const;

function passesCategory(b: ConnectionBrokerOption, f: CategoryFilter): boolean {
  return f === "all" || b.category === f;
}

function passesMethod(b: ConnectionBrokerOption, f: MethodFilter): boolean {
  if (f === "all") return true;
  if (f === "coming") {
    return b.status === "coming_v1_1" || b.status === "coming_v1_2_lite";
  }
  // oauth / import filters intentionally show ONLY available brokers so
  // the "Coming" tab is the single home for not-yet-shipped integrations.
  return b.status === "available" && b.method === f;
}

function GridSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-label="Loading brokers"
      aria-busy
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <ChartGlassCard
          key={i}
          level="resting"
          padding="md"
          as="div"
          className="h-[150px]"
        >
          <div className="flex h-full flex-col gap-3">
            <div className="flex items-start gap-3">
              <Skeleton className="size-11 rounded-md" />
              <div className="flex flex-1 flex-col gap-2">
                <Skeleton className="h-3.5 w-2/3" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
            <div className="mt-auto flex justify-end">
              <Skeleton className="h-8 w-20" />
            </div>
          </div>
        </ChartGlassCard>
      ))}
    </div>
  );
}

export default function ConnectAccounts() {
  const navigate = useNavigate();
  const [categoryFilter, setCategoryFilter] =
    React.useState<CategoryFilter>("all");
  const [methodFilter, setMethodFilter] = React.useState<MethodFilter>("all");
  const [notifyState, setNotifyState] = React.useState<{
    slug: string;
    name: string;
  } | null>(null);

  const query = useQuery({
    queryKey: ["connect-hub", "options"],
    queryFn: () => connectHubApi.options(),
    staleTime: 60_000,
  });

  const handleConnectOAuth = React.useCallback(
    (_broker: ConnectionBrokerOption) => {
      // The existing OAuth wiring lives on Settings → Connections (Schwab,
      // Tastytrade, IBKR). Hand off there rather than reimplementing OAuth.
      navigate("/settings/connections");
    },
    [navigate],
  );

  const handleImport = React.useCallback(
    (broker: ConnectionBrokerOption) => {
      navigate(`/portfolio/import?broker=${broker.slug}`);
    },
    [navigate],
  );

  const handleNotifyMe = React.useCallback((broker: ConnectionBrokerOption) => {
    setNotifyState({ slug: broker.slug, name: broker.name });
  }, []);

  const handleManage = React.useCallback(() => {
    navigate("/accounts/manage");
  }, [navigate]);

  const handleLitePricing = React.useCallback(() => {
    navigate("/pricing");
  }, [navigate]);

  const allBrokers = query.data?.brokers ?? [];
  const filtered = React.useMemo(
    () =>
      allBrokers.filter(
        (b) => passesCategory(b, categoryFilter) && passesMethod(b, methodFilter),
      ),
    [allBrokers, categoryFilter, methodFilter],
  );

  const connectedCount = allBrokers.reduce(
    (acc, b) => acc + (b.user_state.connected ? 1 : 0),
    0,
  );

  return (
    <Page>
      <PageHeader
        title="Connect an account"
        subtitle="Sync via OAuth where the broker offers it. Otherwise import a CSV — every broker your money lives at, all in one place."
        rightContent={
          <Button
            type="button"
            variant="outline"
            size="sm"
            asChild
          >
            <Link to="/accounts/manage">Manage connections</Link>
          </Button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Type</span>
          <SegmentedPeriodSelector
            ariaLabel="Filter by broker category"
            size="sm"
            options={CATEGORY_OPTIONS}
            value={categoryFilter}
            onChange={(v) => setCategoryFilter(v as CategoryFilter)}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Method</span>
          <SegmentedPeriodSelector
            ariaLabel="Filter by connection method"
            size="sm"
            options={METHOD_OPTIONS}
            value={methodFilter}
            onChange={(v) => setMethodFilter(v as MethodFilter)}
          />
        </div>
        {connectedCount > 0 ? (
          <span className="ml-auto text-xs text-muted-foreground">
            {connectedCount} connected
          </span>
        ) : null}
      </div>

      {query.isLoading ? (
        <GridSkeleton />
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load brokers"
          description="The connection catalog failed to load. This is almost always a transient backend hiccup."
          error={query.error}
          retry={() => query.refetch()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No brokers match these filters"
          description="Try a different category or connection method."
          action={{
            label: "Reset filters",
            onClick: () => {
              setCategoryFilter("all");
              setMethodFilter("all");
            },
          }}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((broker) => (
            <BrokerCard
              key={broker.slug}
              broker={broker}
              onConnectOAuth={handleConnectOAuth}
              onImport={handleImport}
              onNotifyMe={handleNotifyMe}
              onManage={handleManage}
              onLitePricing={handleLitePricing}
            />
          ))}
        </div>
      )}

      {notifyState ? (
        <NotifyMeDialog
          open={Boolean(notifyState)}
          onOpenChange={(open) => {
            if (!open) setNotifyState(null);
          }}
          brokerSlug={notifyState.slug}
          brokerName={notifyState.name}
        />
      ) : null}
    </Page>
  );
}
