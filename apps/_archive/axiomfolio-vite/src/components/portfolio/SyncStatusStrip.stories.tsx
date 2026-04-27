import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ColorModeProvider } from "@/theme/colorMode";
import { SyncStatusStrip } from "./SyncStatusStrip";
import { Skeleton } from "@/components/ui/skeleton";

export default {
  title: "Portfolio / SyncStatusStrip",
};

const T0 = "2026-04-22T12:00:00.000Z";
const tFresh = (m: number) => new Date(new Date(T0).getTime() - m * 60_000).toISOString();
const tHoursAgo = (h: number) => new Date(new Date(T0).getTime() - h * 3_600_000).toISOString();

function wrap(client: QueryClient, body: React.ReactNode) {
  return (
    <ColorModeProvider>
      <QueryClientProvider client={client}>
        <div className="max-w-xl p-4">{body}</div>
      </QueryClientProvider>
    </ColorModeProvider>
  );
}

/** Ladle cannot run the same pending-query path as the live hook without a mock; this mirrors the strip skeleton. */
export const Loading = () => {
  return (
    <div className="max-w-xl p-4">
      <p className="mb-2 text-xs text-muted-foreground">
        Matches `data-state=&quot;loading&quot;` in unit tests: skeleton row + optional Sync button slot.
      </p>
      <div className="flex w-full min-w-0 max-w-2xl items-center gap-2">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-20 shrink-0 rounded-md" />
      </div>
    </div>
  );
};

export const Empty = () => {
  const client = new QueryClient();
  client.setQueryData(["portfolioAccounts"], []);
  return wrap(
    client,
    <>
      <p className="mb-2 text-xs text-muted-foreground">No connected accounts: component returns null.</p>
      <SyncStatusStrip className="mb-0" />
    </>
  );
};

export const AllHealthy = () => {
  const client = new QueryClient();
  client.setQueryData(
    ["portfolioAccounts"],
    [
      { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: tFresh(30), sync_status: "success" },
      { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: tFresh(10), sync_status: "success" },
    ]
  );
  return wrap(
    client,
    <SyncStatusStrip showSyncButton className="mb-0" />
  );
};

export const OneStale = () => {
  const client = new QueryClient();
  client.setQueryData(
    ["portfolioAccounts"],
    [
      { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: tFresh(20), sync_status: "success" },
      { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: tHoursAgo(7), sync_status: "success" },
    ]
  );
  return wrap(
    client,
    <SyncStatusStrip showSyncButton className="mb-0" />
  );
};

export const OneFailed = () => {
  const client = new QueryClient();
  client.setQueryData(
    ["portfolioAccounts"],
    [
      { id: 1, broker: "ibkr", account_number: "U1000001", last_successful_sync: tFresh(5), sync_status: "success" },
      { id: 2, broker: "tasty", account_number: "U2000002", last_successful_sync: null, sync_status: "never_synced" },
    ]
  );
  return wrap(
    client,
    <SyncStatusStrip showSyncButton className="mb-0" />
  );
};

export const MultipleFailed = () => {
  const client = new QueryClient();
  client.setQueryData(
    ["portfolioAccounts"],
    [
      { id: 1, broker: "ibkr", account_number: "A1", last_successful_sync: null, sync_status: "never_synced" },
      { id: 2, broker: "tasty", account_number: "A2", last_successful_sync: tHoursAgo(12), sync_status: "error" },
      { id: 3, broker: "schwab", account_number: "A3", last_successful_sync: tFresh(1), sync_status: "success" },
    ]
  );
  return wrap(
    client,
    <SyncStatusStrip showSyncButton className="mb-0" />
  );
};

/** Pending mutation is not forced here; see unit test for spinner while syncing. */
export const Syncing = () => {
  const client = new QueryClient();
  client.setQueryData(
    ["portfolioAccounts"],
    [{ id: 1, broker: "ibkr", account_number: "U1", last_successful_sync: tFresh(2), sync_status: "success" }]
  );
  return wrap(
    client,
    <>
      <p className="mb-2 text-xs text-muted-foreground">Click &quot;Sync&quot; to see the pending spinner in the live app.</p>
      <SyncStatusStrip showSyncButton className="mb-0" />
    </>
  );
};
