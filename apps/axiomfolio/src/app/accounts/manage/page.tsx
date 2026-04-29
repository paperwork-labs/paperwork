"use client";

/**
 * AccountsManagement (`/accounts/manage`) — manage existing connections.
 *
 * Lightweight cousin of `SettingsConnections.tsx`. The Connect hub
 * (`/connect`) routes "Manage" CTAs here so users land on a focused
 * page instead of the busier settings shell. Scope per the v1 plan
 * (3h shell): rename, disconnect, last-synced-at. Sync history links
 * out to the existing system status page.
 */

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { Check, Loader2, Pencil, Plug, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChartGlassCard } from "@/components/ui/ChartGlassCard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/input";
import { Page, PageHeader } from "@paperwork-labs/ui";
import { Skeleton } from "@/components/ui/skeleton";
import { useBackendUser } from "@/hooks/use-backend-user";
import { accountsApi, handleApiError } from "@/services/api";
import { cn } from "@/lib/utils";
import { isPlatformAdminRole } from "@/utils/userRole";

import { BrokerLogo } from "@/components/connect/BrokerLogo";
import { RequireAuthClient } from "@/components/auth/RequireAuthClient";

interface ManagedAccount {
  id: number;
  broker: string;
  account_number: string;
  account_name?: string | null;
  account_type: string;
  status: string;
  is_enabled: boolean;
  last_successful_sync?: string | null;
  sync_status?: string | null;
  sync_error_message?: string | null;
}

const BROKER_DISPLAY: Record<string, string> = {
  schwab: "Charles Schwab",
  ibkr: "Interactive Brokers",
  tastytrade: "Tastytrade",
  fidelity: "Fidelity",
  robinhood: "Robinhood",
};

function brokerLabel(broker: string): string {
  const key = (broker || "").toLowerCase();
  return BROKER_DISPLAY[key] ?? broker;
}

function brokerLogoUrl(broker: string): string {
  const key = (broker || "").toLowerCase();
  return `/broker-logos/${key}.svg`;
}

function formatAbsoluteSync(iso: string | null | undefined): string {
  if (!iso) return "Never synced";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "Never synced";
  const diffMs = Date.now() - dt.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60_000));
  if (minutes < 1) return "Synced just now";
  if (minutes < 60) return `Synced ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Synced ${hours} hr ago`;
  const days = Math.round(hours / 24);
  return `Synced ${days} day${days === 1 ? "" : "s"} ago`;
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-label="Loading connections" aria-busy>
      {Array.from({ length: 3 }).map((_, i) => (
        <ChartGlassCard key={i} level="resting" padding="md" className="h-[88px]">
          <div className="flex h-full items-center gap-3">
            <Skeleton className="size-10 rounded-md" />
            <div className="flex flex-1 flex-col gap-2">
              <Skeleton className="h-3.5 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-8 w-20" />
          </div>
        </ChartGlassCard>
      ))}
    </div>
  );
}

function AccountRow({
  account,
  onRename,
  onDisconnect,
  isMutating,
  showSyncHistory,
}: {
  account: ManagedAccount;
  onRename: (id: number, name: string) => Promise<void>;
  onDisconnect: (id: number) => void;
  isMutating: boolean;
  showSyncHistory: boolean;
}) {
  const [editing, setEditing] = React.useState(false);
  const [name, setName] = React.useState(account.account_name ?? "");

  React.useEffect(() => {
    setName(account.account_name ?? "");
  }, [account.account_name]);

  const handleSave = async () => {
    const trimmed = name.trim();
    if (trimmed === (account.account_name ?? "").trim()) {
      setEditing(false);
      return;
    }
    try {
      await onRename(account.id, trimmed);
      setEditing(false);
    } catch {
      // toast surfaced by parent mutation handler
    }
  };

  const isErrored =
    account.sync_status && ["error", "failed"].includes(String(account.sync_status).toLowerCase());

  return (
    <ChartGlassCard
      level="resting"
      padding="md"
      as="article"
      ariaLabel={`${brokerLabel(account.broker)} ${account.account_number}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <BrokerLogo
          slug={String(account.broker || "ibkr").toLowerCase()}
          name={brokerLabel(account.broker)}
          remoteLogoUrl={brokerLogoUrl(account.broker)}
          size={40}
        />

        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="flex items-center gap-2">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Account nickname"
                autoFocus
                className="h-8 max-w-[280px]"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleSave();
                  if (e.key === "Escape") {
                    setName(account.account_name ?? "");
                    setEditing(false);
                  }
                }}
              />
              <Button
                type="button"
                size="icon-sm"
                variant="outline"
                onClick={() => void handleSave()}
                aria-label="Save account name"
                disabled={isMutating}
              >
                <Check className="size-3" aria-hidden />
              </Button>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={() => {
                  setName(account.account_name ?? "");
                  setEditing(false);
                }}
                aria-label="Cancel rename"
              >
                <X className="size-3" aria-hidden />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h3 className="truncate font-heading text-sm font-medium text-foreground">
                {account.account_name?.trim() || `${brokerLabel(account.broker)} · ${account.account_number}`}
              </h3>
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                onClick={() => setEditing(true)}
                aria-label="Rename account"
              >
                <Pencil className="size-3" aria-hidden />
              </Button>
            </div>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{account.account_number}</span>
            <span>·</span>
            <span>{formatAbsoluteSync(account.last_successful_sync)}</span>
            {isErrored ? (
              <Badge variant="destructive" className={cn("h-4 text-[10px]")} title={account.sync_error_message ?? undefined}>
                Sync error
              </Badge>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {showSyncHistory ? (
            <Button asChild type="button" size="sm" variant="outline">
              <Link href="/settings/admin/system">Sync history</Link>
            </Button>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onDisconnect(account.id)}
            disabled={isMutating}
            aria-label="Disconnect account"
          >
            <Trash2 className="size-3.5" aria-hidden />
            Disconnect
          </Button>
        </div>
      </div>
    </ChartGlassCard>
  );
}

function AccountsManagementContent() {
  const router = useRouter();
  const { user: currentUser } = useBackendUser();
  const showSyncHistory = isPlatformAdminRole(currentUser?.role);
  const queryClient = useQueryClient();
  const [confirmDisconnectId, setConfirmDisconnectId] = React.useState<number | null>(null);

  const query = useQuery<ManagedAccount[]>({
    queryKey: ["accounts-manage", "list"],
    queryFn: async () => {
      const res = (await accountsApi.list()) as ManagedAccount[];
      return Array.isArray(res) ? res : [];
    },
    staleTime: 30_000,
  });

  const renameMutation = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      return accountsApi.updateAccount(id, { account_name: name || undefined });
    },
    onSuccess: () => {
      toast.success("Renamed");
      queryClient.invalidateQueries({ queryKey: ["accounts-manage", "list"] });
    },
    onError: (err) => toast.error(`Rename failed: ${handleApiError(err)}`),
  });

  const disconnectMutation = useMutation({
    mutationFn: async (id: number) => accountsApi.remove(id),
    onSuccess: () => {
      toast.success("Disconnected");
      setConfirmDisconnectId(null);
      queryClient.invalidateQueries({ queryKey: ["accounts-manage", "list"] });
      queryClient.invalidateQueries({ queryKey: ["connect-hub", "options"] });
    },
    onError: (err) => toast.error(`Disconnect failed: ${handleApiError(err)}`),
  });

  const accounts = query.data ?? [];

  return (
    <Page>
      <PageHeader
        title="Manage connections"
        subtitle="Rename, disconnect, or review the sync status of every connected broker account."
        rightContent={
          <Button asChild type="button" size="sm">
            <Link href="/connect">
              <Plug aria-hidden />
              Connect another
            </Link>
          </Button>
        }
      />

      {query.isLoading ? (
        <ListSkeleton />
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load your connections"
          description="The accounts API failed to respond. This is almost always transient."
          error={query.error}
          retry={() => query.refetch()}
        />
      ) : accounts.length === 0 ? (
        <EmptyState
          icon={Plug}
          title="You haven't connected any accounts yet."
          description="Sync via OAuth where available, or import a CSV from any broker."
          action={{
            label: "Connect an account",
            onClick: () => {
              router.push("/connect");
            },
          }}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {accounts.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              showSyncHistory={showSyncHistory}
              isMutating={
                (renameMutation.isPending && renameMutation.variables?.id === account.id) ||
                (disconnectMutation.isPending && disconnectMutation.variables === account.id)
              }
              onRename={async (id, name) => {
                await renameMutation.mutateAsync({ id, name });
              }}
              onDisconnect={(id) => setConfirmDisconnectId(id)}
            />
          ))}
        </div>
      )}

      <Dialog
        open={confirmDisconnectId !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDisconnectId(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect this account?</DialogTitle>
            <DialogDescription>
              We&apos;ll stop syncing and remove the credentials. Historical positions and trades stay in your
              portfolio. You can reconnect at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setConfirmDisconnectId(null)}
              disabled={disconnectMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                if (confirmDisconnectId !== null) {
                  disconnectMutation.mutate(confirmDisconnectId);
                }
              }}
              disabled={disconnectMutation.isPending}
            >
              {disconnectMutation.isPending ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  Disconnecting…
                </>
              ) : (
                "Disconnect"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Page>
  );
}

export default function AccountsManagementPage() {
  return (
    <RequireAuthClient>
      <AccountsManagementContent />
    </RequireAuthClient>
  );
}
