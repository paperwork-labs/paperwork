import * as React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";

import { Button } from "@/components/ui/button";
import AppLogo from "@/components/ui/AppLogo";
import { indicatorTogglesFromShareList } from "@/lib/chartShareToggles";
import { fetchPublicShareChartBars } from "@/services/chartShare";
import { cn } from "@/lib/utils";
import SymbolChartWithMarkers from "@/components/charts/SymbolChartWithMarkers";

const ChartShare: React.FC = () => {
  const { token } = useParams<{ token: string }>();

  const q = useQuery({
    queryKey: ["public-share-chart", token],
    queryFn: () => {
      if (!token) {
        return Promise.reject(new Error("Missing share token"));
      }
      return fetchPublicShareChartBars(token);
    },
    enabled: Boolean(token),
    retry: false,
  });

  const toggles = React.useMemo(
    () => indicatorTogglesFromShareList(q.data?.indicators),
    [q.data?.indicators],
  );

  if (!token) {
    return (
      <div className="min-h-screen bg-background px-4 py-10 text-foreground">
        <div className="mx-auto max-w-3xl text-center text-sm text-muted-foreground">
          This page needs a share link. Ask whoever sent you here for a valid URL.
        </div>
      </div>
    );
  }

  if (q.isLoading) {
    return (
      <div className="min-h-screen bg-background px-4 py-8 text-foreground">
        <div className="mx-auto max-w-5xl">
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <AppLogo size={28} />
              <span>Shared from AxiomFolio</span>
            </div>
          </div>
          <div
            className="flex min-h-[320px] items-center justify-center"
            role="status"
            aria-live="polite"
          >
            <div className="flex flex-col items-center gap-2">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
              <p className="text-sm text-muted-foreground">Loading shared chart data…</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (q.isError) {
    const status = isAxiosError(q.error) ? q.error.response?.status : undefined;
    const detail = isAxiosError(q.error)
      ? (q.error.response?.data as { detail?: string } | undefined)?.detail
      : null;
    const message =
      status === 401
        ? "This link expired or the URL was copied incorrectly. Request a new share from the owner."
        : status === 404
          ? "We have no market history for that symbol in this window yet. The owner can try again after the daily data pipeline runs."
          : status === 503
            ? "Our market data provider is not responding. Try again in a few minutes."
            : detail && typeof detail === "string"
              ? detail
              : "We could not load this shared chart. Check your network and try again.";

    return (
      <div className="min-h-screen bg-background px-4 py-10 text-foreground">
        <div className="mx-auto max-w-lg text-center">
          <p className="text-sm text-muted-foreground" role="alert">
            {message}
          </p>
          <Button className="mt-6" asChild variant="default">
            <Link to="/register">Create a free account</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (!q.data) {
    return null;
  }

  const { bars, symbol, period: _p } = q.data;
  if (bars.length === 0) {
    return (
      <div className="min-h-screen bg-background px-4 py-10 text-foreground">
        <div className="mx-auto max-w-3xl text-center text-sm text-muted-foreground" role="status">
          There are no price bars in this range yet for {symbol}. The snapshot may still be
          building—check back after the next market data refresh.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground">
      <div className="mx-auto max-w-6xl">
        <header className="mb-4 flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <AppLogo size={36} />
            <div>
              <p className="text-sm font-medium text-foreground">Shared from AxiomFolio</p>
              <p className="text-xs text-muted-foreground">
                Read-only chart for {symbol} — same studies the owner selected when they created
                this link.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="default" size="sm">
              <Link to="/register">Sign up free</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/login">Log in</Link>
            </Button>
          </div>
        </header>

        <div
          className={cn(
            "overflow-hidden rounded-xl border border-border bg-card/30 p-2 shadow-sm",
            "min-h-0",
          )}
        >
          <SymbolChartWithMarkers
            bars={bars}
            events={[]}
            symbol={symbol}
            showEvents={false}
            readOnly
            indicators={toggles}
            height={480}
            zoomYears="all"
          />
        </div>
      </div>
    </div>
  );
};

export default ChartShare;
